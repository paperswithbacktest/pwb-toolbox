"""A bar's sales fund its purchases, and an overnight gap is not a reason to shrink a book.

Two defects of 0.1.31-0.1.52 found by the replication pass of 2026-11-18:

* the broker checks a bar's orders as one batch in submission order, against
  a running cash that carries a refused buy's cost to the next order; a
  strategy that rebalances name by name sends the buy before the sale that
  funds it, and every buy behind it is refused (``the_law_of_small_numbers…``,
  64 of 67 refusals) -- and then the whole run was re-run at 90 %, three times;
* an order accepted at the close it was sized on and refused at the next open
  because the price gapped up counted towards the same 2 % tolerance: a 99 %
  book was re-run at 89.1 % (``the_case_for_risk_managed_gold``). Not counting
  them is not enough -- the purchases refused are those of the days the asset
  opens higher -- so such a run is re-run once with the cash its largest gap
  needed (93.4 % there).

Each scenario fails on 0.1.52.
"""

import unittest
from unittest import mock

import numpy as np

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be

from _synthetic import offline, panel


class _Harnessed(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True


def _run(prices, strategy_cls, symbols, commission=0.0, **kwargs):
    with offline(prices):
        return be.run_strategy(
            indicator_cls=None,
            indicator_kwargs={},
            strategy_cls=strategy_cls,
            strategy_kwargs={},
            symbols=list(symbols),
            start_date="2020-01-01",
            cash=100_000.0,
            broker_kwargs={"commission": commission},
            **kwargs,
        )


def _as_sent(broker):
    """0.1.52: the batch checked in the order the strategy sent it."""
    return {"batches": 0, "orders": 0, "first": None, "last": None}


class Rotation(_Harnessed):
    """All in one of two names, switched every 5 bars, targets sent in feed order.

    Switching back to A sends A's buy before B's sale: the buy needs 98 % of
    the NAV while the cash holds 2 %.
    """

    params = (("weight", 0.98), ("extra", 0.0))

    def next(self):
        super().next()
        i = len(self)
        if i % 5 == 1:
            hold_a = (i // 5) % 2 == 0
            a, b = self.datas[0], self.datas[1]
            self.order_target_percent(a, self.p.weight if hold_a else 0.0)
            self.order_target_percent(b, 0.0 if hold_a else self.p.weight)
            if self.p.extra and len(self.datas) > 2:
                self.order_target_percent(self.datas[2], self.p.extra)


def _flat(n=60, names=("A", "B")):
    return panel({name: np.full(n, 100.0) for name in names})


class SellsFirstTest(unittest.TestCase):
    def test_a_rotation_is_funded_by_its_own_sales(self):
        strategy = _run(_flat(), Rotation, ("A", "B"))
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertEqual(strategy.run_report["attempts"], 1)
        self.assertEqual(strategy.run_report["step_cap"], 1.0)
        self.assertGreater(strategy.sells_first_audit["batches"], 0)
        # the book is where the strategy asked: 980 shares of the last name held
        sizes = [strategy.getposition(d).size for d in strategy.datas]
        self.assertEqual(sorted(sizes), [0.0, 980.0])

    def test_the_same_rotation_as_sent_is_refused(self):
        # what 0.1.52 did: the buys refused, then the whole run re-run smaller
        with mock.patch.object(be, "_check_sells_first", _as_sent):
            strategy = _run(_flat(), Rotation, ("A", "B"))
        # five steps down to 59 %, none funded, the refused run returned
        self.assertEqual(strategy.run_report["attempts"], 1 + be.DELEVERAGE_MAX_STEPS)
        self.assertGreater(strategy.funding_audit["margin_check"], 0)
        self.assertTrue(strategy.run_report["underfunded"])

    def test_a_batch_the_account_funds_is_left_as_sent(self):
        class Small(Rotation):
            params = (("weight", 0.30),)

        strategy = _run(_flat(), Small, ("A", "B"))
        with mock.patch.object(be, "_check_sells_first", _as_sent):
            reference = _run(_flat(), Small, ("A", "B"))
        self.assertEqual(strategy.sells_first_audit["batches"], 0)
        self.assertEqual(
            [x["value"] for x in strategy.log_data],
            [x["value"] for x in reference.log_data],
        )

    def test_a_book_over_the_account_after_its_sales_is_still_refused(self):
        # 98 % rotated plus 50 % in a third name: 148 % long whatever the order
        class Over(Rotation):
            params = (("extra", 0.50),)

        strategy = _run(_flat(names=("A", "B", "C")), Over, ("A", "B", "C"))
        as_published = strategy.run_report["funding_as_published"]
        self.assertIsNotNone(as_published)
        self.assertGreater(as_published["margin_check"], 0)
        self.assertGreater(strategy.run_report["attempts"], 1)


class GapRotation(_Harnessed):
    """All in one of two names at 99 %, sales sent first, switched every 10 bars."""

    def next(self):
        super().next()
        i = len(self)
        if i % 10 == 1:
            hold_a = (i // 10) % 2 == 0
            a, b = self.datas[0], self.datas[1]
            if hold_a:
                self.order_target_percent(b, 0.0)
                self.order_target_percent(a, 0.99)
            else:
                self.order_target_percent(a, 0.0)
                self.order_target_percent(b, 0.99)


class OvernightGapTest(unittest.TestCase):
    def _prices(self):
        n = 60
        close = {"A": np.full(n, 100.0), "B": np.full(n, 100.0)}
        # every purchase fills at an open 3 % above the close it was sized on
        opens = {"A": np.full(n, 103.0), "B": np.full(n, 103.0)}
        opens["A"][0] = opens["B"][0] = 100.0
        return panel(close, opens=opens)

    def test_a_gap_is_cushioned_once_not_stepped_down(self):
        strategy = _run(self._prices(), GapRotation, ("A", "B"))
        first = strategy.run_report["funding_as_published"]
        # as published: fundable at the close, refused at an open 3 % higher,
        # more than 2 % of the orders -- 0.1.52 re-ran it at 90 % of itself
        self.assertEqual(first["margin_check"], 0)
        self.assertGreater(first["margin_fill"], 0)
        self.assertGreater(first["reject_rate"], be.MARGIN_TOLERANCE)
        self.assertAlmostEqual(first["max_fill_gap"], 1.03)
        # once, at the cash the gap needed: 99 % / 1.03, not 90 %
        report = strategy.run_report
        self.assertEqual(report["attempts"], 2)
        self.assertEqual(report["deleverage_steps"], 0)
        self.assertAlmostEqual(report["gap_cushion"], 1 / 1.03)
        self.assertAlmostEqual(report["exposure_cap"], 1 / 1.03)
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertFalse(report["underfunded"])

    def test_a_cushion_is_never_deeper_than_a_step(self):
        prices = self._prices()
        for name in ("A", "B"):
            prices.loc[prices.index[1]:, (name, "open")] = 130.0
            prices[(name, "high")] = prices[[(name, "open"), (name, "close")]].max(axis=1)
        strategy = _run(prices, GapRotation, ("A", "B"))
        self.assertEqual(strategy.run_report["gap_cushion"], be.DELEVERAGE_STEP)
        self.assertEqual(strategy.run_report["attempts"], 2)


class UnderfundedCriterionTest(unittest.TestCase):
    def _audit(self, **kw):
        audit = {"margin": 50, "submitted": 100, "reject_rate": 0.5,
                 "min_cash": 0.0, "min_cash_ratio": 0.0, "min_value": 1.0}
        audit.update(kw)
        return audit

    def test_refusals_at_the_fill_are_not_counted(self):
        audit = self._audit(margin_check=0, margin_fill=50, funding_reject_rate=0.0)
        self.assertFalse(be._underfunded(audit, 0.02))

    def test_refusals_of_the_check_are(self):
        audit = self._audit(margin_check=50, margin_fill=0, funding_reject_rate=0.5)
        self.assertTrue(be._underfunded(audit, 0.02))

    def test_an_audit_without_the_split_is_read_as_before(self):
        self.assertTrue(be._underfunded(self._audit(), 0.02))


if __name__ == "__main__":
    unittest.main()
