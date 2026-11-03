"""A strategy's own ``broker.setcommission`` can raise its fees, never lower them.

The harness registers one measured scheme per symbol before the strategy is
built, and a named scheme always wins over the default one, so up to 0.1.42 a
strategy's ``self.broker.setcommission(commission=0.01)`` set a scheme nothing
consulted. The probe of PR #62: 1 bp measured on ``A`` and 1 % asked by the
strategy charged **0.10** on a 1 000 fill instead of **10.00**.

Rule since 0.1.43: each fill pays the higher of the two. Runs on whichever
engine ``pwb_toolbox.engine`` selected (backtrader or Tradewind).
"""

import unittest
from unittest import mock

import pwb_toolbox.backtesting as pwb_bt
from pwb_toolbox.backtesting import BaseStrategy, bt
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.backtesting.commission import Cost

from _synthetic import offline, panel

MEASURED = 0.0001  # 1 bp on A
PRICE = 100.0
SIZE = 10  # a 1 000 fill


def _strategy(**setcommission):
    class Probe(BaseStrategy):
        params = (("indicator_cls", None), ("indicator_kwargs", {}))

        def __init__(self):
            super().__init__()
            self.pbar.disable = True
            self.fills = []
            if setcommission:
                self.broker.setcommission(**setcommission)

        def notify_order(self, order):
            if order.status == order.Completed:
                self.fills.append(order.executed.comm)

        def next(self):
            super().next()
            if len(self.datas[0]) == 2:
                self.buy(data=self.datas[0], size=SIZE)

    return Probe


def _run(strategy_cls, symbols=("A",)):
    prices = panel({s: [PRICE] * 30 for s in symbols})
    schedules = {s: {2020: MEASURED} for s in symbols}
    summary = {s: Cost(s, MEASURED, "measured", 2020) for s in symbols}
    with offline(prices), mock.patch.object(
        pwb_bt, "get_cost_schedules", lambda *a, **k: (schedules, summary)
    ), mock.patch.object(pwb_bt, "equity_symbols", lambda s: set(s)), mock.patch.object(
        pwb_bt, "currency_symbols", lambda s: {}
    ):
        return be.run_strategy(
            indicator_cls=None,
            indicator_kwargs={},
            strategy_cls=strategy_cls,
            strategy_kwargs={},
            symbols=list(symbols),
            start_date="2020-01-01",
            cash=100_000.0,
        )


class HigherOfTheTwo(unittest.TestCase):
    def assertCharged(self, strategy, amount):
        self.assertEqual(len(strategy.fills), 1)
        self.assertAlmostEqual(strategy.fills[0], amount, places=9)

    def test_measured_spread_without_a_request(self):
        strategy = _run(_strategy())
        self.assertCharged(strategy, 0.10)
        self.assertEqual(strategy.run_report["commission_policy"]["calls"], [])

    def test_probe_one_percent_is_charged(self):
        strategy = _run(_strategy(commission=0.01))
        self.assertCharged(strategy, 10.00)
        policy = strategy.run_report["commission_policy"]
        self.assertEqual(policy["mode"], "higher_of_measured_and_strategy")
        self.assertAlmostEqual(policy["floor_perc"], 0.01)
        self.assertEqual(policy["raised_symbols"], 1)

    def test_zero_changes_nothing(self):
        strategy = _run(_strategy(commission=0.0))
        self.assertCharged(strategy, 0.10)
        self.assertEqual(strategy.run_report["commission_policy"]["raised_symbols"], 0)

    def test_below_the_measured_spread_changes_nothing(self):
        strategy = _run(_strategy(commission=0.00001))
        self.assertCharged(strategy, 0.10)

    def test_percabs_false_reads_percent(self):
        strategy = _run(_strategy(commission=1.0, percabs=False))
        self.assertCharged(strategy, 10.00)

    def test_per_unit_fee_when_dearer(self):
        strategy = _run(_strategy(commission=2.0, commtype=bt.CommInfoBase.COMM_FIXED))
        self.assertCharged(strategy, 20.00)

    def test_per_unit_fee_when_cheaper(self):
        strategy = _run(_strategy(commission=0.001, commtype=bt.CommInfoBase.COMM_FIXED))
        self.assertCharged(strategy, 0.10)

    def test_futures_terms_are_not_taken(self):
        # A margin makes the legacy scheme per-unit; margin and mult are ignored
        # (the stock stays a stock), only the fee competes with the spread.
        strategy = _run(_strategy(commission=1.0, margin=2000.0, mult=50.0))
        self.assertCharged(strategy, 10.00)
        call = strategy.run_report["commission_policy"]["calls"][0]
        self.assertEqual(call["kind"], "fixed")
        self.assertEqual(call["ignored"], ["margin", "mult"])

    def test_named_request_only_touches_that_name(self):
        strategy = _run(_strategy(commission=0.01, name="B"), symbols=("A", "B"))
        self.assertCharged(strategy, 0.10)  # the fill is on A
        strategy = _run(_strategy(commission=0.01, name="A"), symbols=("A", "B"))
        self.assertCharged(strategy, 10.00)

    def test_caller_commission_still_bypasses_the_measured_schemes(self):
        prices = panel({"A": [PRICE] * 30})
        with offline(prices):
            strategy = be.run_strategy(
                indicator_cls=None, indicator_kwargs={}, strategy_cls=_strategy(),
                strategy_kwargs={}, symbols=["A"], start_date="2020-01-01",
                cash=100_000.0, broker_kwargs={"commission": 0.002},
            )
        self.assertCharged(strategy, 2.00)
        self.assertEqual(strategy.run_report["commission_policy"]["mode"], "caller")


if __name__ == "__main__":
    unittest.main()
