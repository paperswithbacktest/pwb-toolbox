"""Two orders on one name in one bar: executed as before, but counted and reported.

backtrader sizes ``order_target_*`` on the position as it stands, blind to the
orders not yet filled. ``lazy_prices`` activated a cohort and expired another
on the same bar, each with its own ``order_target_size`` per name, and doubled
or flipped its book every month until the NAV went negative;
``profitable_mean_reversion`` called ``close()`` twice and then
``order_target_size`` and doubled its sizes every day. The harness accepted
both silently. It still executes them (the default behaviour is unchanged) but
counts them in ``same_bar_orders`` and warns.
"""

import contextlib
import io
import unittest

import numpy as np

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.backtesting import checks

from _synthetic import offline, panel

N = 60


def _prices():
    rng = np.random.default_rng(3)
    return panel({
        "A": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, N))),
        "B": 50 * np.exp(np.cumsum(rng.normal(0, 0.01, N))),
    })


class _Base(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.held = {}

    def next(self):
        super().next()
        i = len(self) - 1
        self.held[i] = self.getposition(self.datas[0]).size
        self.step(i)

    def step(self, i):
        pass


class OneTargetPerBar(_Base):
    def step(self, i):
        if i == 5:
            self.order_target_size(self.datas[0], 100)
        elif i == 20:
            self.order_target_size(self.datas[0], 0)


class CloseThenTargetZero(_Base):
    """The profitable_mean_reversion pattern: close(), then a target of 0 on the same bar."""

    def step(self, i):
        if i == 5:
            self.order_target_size(self.datas[0], 100)
        elif i == 20:
            self.close(self.datas[0])
            self.order_target_size(self.datas[0], 0)


class TwoCohorts(_Base):
    """The lazy_prices pattern: one cohort enters and one leaves, each retargets the name."""

    def step(self, i):
        if i == 5:
            self.order_target_size(self.datas[0], 100)
        elif i == 20:
            self.order_target_size(self.datas[0], 150)  # the new cohort's book
            self.order_target_size(self.datas[0], 50)  # the old one expires


class ExplicitSplitSale(_Base):
    """Two plain sells on the same bar: intended, counted, but not a target."""

    def step(self, i):
        if i == 5:
            self.buy(self.datas[0], size=100)
        elif i == 20:
            self.sell(self.datas[0], size=40)
            self.sell(self.datas[0], size=60)


class SameBarOrdersTest(unittest.TestCase):
    def run_one(self, cls):
        out = io.StringIO()
        with offline(_prices()), contextlib.redirect_stdout(out):
            strategy = be.run_strategy(
                indicator_cls=None, indicator_kwargs={}, strategy_cls=cls,
                strategy_kwargs={}, symbols=["A", "B"], start_date="2020-01-01",
                cash=100_000.0, broker_kwargs={"commission": 0.0},
            )
        return strategy, out.getvalue()

    def test_one_order_per_bar_reports_nothing(self):
        strategy, printed = self.run_one(OneTargetPerBar)
        self.assertEqual(strategy.same_bar_orders["orders"], 0)
        self.assertEqual(strategy.run_report["same_bar_orders"]["orders"], 0)
        self.assertNotIn("same-bar orders", printed)
        self.assertEqual(strategy.held[25], 0)

    def test_close_then_target_is_counted_and_still_executed(self):
        strategy, printed = self.run_one(CloseThenTargetZero)
        report = strategy.run_report["same_bar_orders"]
        self.assertEqual(report["orders"], 1)
        self.assertEqual(report["targets"], 1)
        self.assertEqual(report["symbols"], 1)
        self.assertEqual(report["bars"], 1)
        example = report["examples"][0]
        self.assertEqual(example["symbol"], "A")
        self.assertEqual(example["earlier"], -100)
        self.assertEqual(example["size"], -100)
        self.assertTrue(example["target"])
        # behaviour unchanged: both sales fill, the long becomes a short
        self.assertEqual(strategy.held[25], -100)
        self.assertIn("Warning: same-bar orders: 1 orders", printed)

    def test_two_cohorts_are_counted(self):
        strategy, _ = self.run_one(TwoCohorts)
        report = strategy.same_bar_orders
        self.assertEqual((report["orders"], report["targets"]), (1, 1))
        # each target saw 100 shares: +50 then -50, the book stays at 100 instead of 50
        self.assertEqual(strategy.held[25], 100)

    def test_explicit_split_sale_is_counted_but_not_as_a_target(self):
        strategy, _ = self.run_one(ExplicitSplitSale)
        report = strategy.same_bar_orders
        self.assertEqual((report["orders"], report["targets"]), (1, 0))
        self.assertEqual(strategy.held[25], 0)

    def test_the_execution_check_warns_on_a_stacked_target(self):
        strategy, _ = self.run_one(CloseThenTargetZero)
        item = {i["id"]: i for i in strategy.checks["items"]}["execution"]
        self.assertEqual(item["status"], "warn")
        self.assertIn("order_target_*", item["summary"])
        self.assertEqual(item["detail"]["sameBarTargets"], 1)

    def test_the_execution_check_still_passes_without_a_target(self):
        strategy, _ = self.run_one(ExplicitSplitSale)
        item = {i["id"]: i for i in strategy.checks["items"]}["execution"]
        self.assertEqual(item["status"], "pass")
        self.assertEqual(item["detail"]["sameBarOrders"], 1)

    def test_check_execution_unchanged_without_the_record(self):
        journal = {"fills": 4, "same_bar": 0, "unmatched": 0, "examples": [],
                   "exectypes": {"Market": 4}}
        self.assertEqual(checks.check_execution(journal, {})["status"], "pass")
        self.assertEqual(
            checks.check_execution(journal, {}, {"orders": 0, "targets": 0})["status"], "pass"
        )


if __name__ == "__main__":
    unittest.main()
