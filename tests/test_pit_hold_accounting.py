"""The books of a position held outside the universe under ``pit_exit="hold"``.

``tests/test_pit_hold.py`` covers the rule; these cover the accounts behind
it. The feed is flat outside the universe and the harness books the
difference with the real price through the cash, so the cases where that
cash could be read as money, double counted or settled at the wrong price
are checked one by one: a short, a name that collapses after it leaves (the
funding audit must not read the mark as a debit), cheat-on-close fills, a
name that stops printing while it is held, and a strategy that trades a
hedge every day (that is not a rebalance of its book).
"""

import unittest
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as pwb_ds
from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.datasets import PIT_UNIVERSES
from pwb_toolbox.datasets import pit_universe

from _synthetic import panel

N = 300
OUT = (105, 200)  # X is not a member on these bars
EVERY = 20  # rebalancing bars: 0, 20, 40, ... (len % 20 == 1)
NEXT = 120  # the first rebalancing bar after X leaves


def _prices(move=1.3, last_print=None, hedge=False):
    """A and B wander; X drifts, then moves by ``move`` between its exit and the rebalance."""
    rng = np.random.default_rng(5)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    b = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    x = 50 * np.exp(np.cumsum(rng.normal(0, 0.002, N)))
    ramp = np.ones(N)
    ramp[OUT[0]:NEXT + 5] = np.linspace(1.0, move, NEXT + 5 - OUT[0])
    ramp[NEXT + 5:] = move
    x = x * ramp
    # X opens away from its previous close, so that a fill at the open and
    # one at the close are told apart
    x_open = np.r_[x[0], x[:-1]] * np.exp(rng.normal(0, 0.01, N))
    if last_print is not None:
        x[last_print + 1:] = np.nan  # delisted
        x_open[last_print + 1:] = np.nan
    series = {"A": a, "B": b, "X": x}
    if hedge:
        series["H"] = 80 * np.exp(np.cumsum(rng.normal(0, 0.005, N)))
    return panel(series, opens={"X": x_open})


def _universe(prices, back=True):
    rows = []
    for i, day in enumerate(prices.index):
        for rank, symbol in enumerate(("A", "B", "X"), start=1):
            if symbol == "X" and i >= OUT[0] and (i < OUT[1] or not back):
                continue
            rows.append((day, symbol, rank))
    return pd.DataFrame(rows, columns=["date", "symbol", "rank"])


class _Recorder(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}), ("coc", False))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        if self.p.coc:
            self.broker.set_coc(True)
        self.held = {}
        self.fills = []
        self.rejected = []

    def notify_order(self, order):
        if order.status == order.Completed:
            self.fills.append(
                (order.data._name, len(self) - 1, order.executed.size, order.executed.price)
            )
        elif order.status in (order.Rejected, order.Margin):
            self.rejected.append((order.data._name, len(self) - 1, order.getstatusname()))

    def next(self):
        super().next()
        self.held[len(self) - 1] = {d._name: self.getposition(d).size for d in self.datas}
        self.step(len(self) - 1)

    def step(self, i):
        pass


class LongX(_Recorder):
    """96 % in A, B and X on bar 100; every 20 bars, equal weight on what is tradable."""

    def step(self, i):
        if i == 100:
            for d in self.datas:
                if d._name != "H":
                    self.order_target_percent(d, 0.32)
        elif i > 100 and i % EVERY == 0:
            names = [d for d in self.datas if d._name != "H" and self.is_tradable(d)]
            for d in self.datas:
                if d._name != "H" and d not in names:
                    self.order_target_percent(d, 0.0)
            for d in names:
                self.order_target_percent(d, 0.96 / len(names))


class ShortX(_Recorder):
    """Short X and long A on bar 100; every 20 bars, retarget A only (the harness closes X)."""

    def step(self, i):
        if i == 100:
            self.order_target_percent(self.getdatabyname("X"), -0.3)
            self.order_target_percent(self.getdatabyname("A"), 0.3)
        elif i > 100 and i % EVERY == 0:
            self.order_target_percent(self.getdatabyname("A"), 0.3)


class LongXWithDailyHedge(LongX):
    """LongX plus an order on the hedge H every day: not a rebalance of the book."""

    def step(self, i):
        super().step(i)
        if i >= 100:
            self.order_target_percent(self.getdatabyname("H"), 0.005 if i % 2 else 0.006)


class TargetsOnlyTheMembers(_Recorder):
    """LongX's first book; at each rebalance, targets for the tradable names only.

    Nothing closes X but the harness, and the purchases need its proceeds.
    """

    def step(self, i):
        if i == 100:
            for d in self.datas:
                self.order_target_percent(d, 0.32)
        elif i > 100 and i % EVERY == 0:
            names = [d for d in self.datas if self.is_tradable(d)]
            for d in names:
                self.order_target_percent(d, 0.96 / len(names))


class _Base(unittest.TestCase):
    prices_kwargs = {}
    back = True

    def setUp(self):
        self.prices = _prices(**self.prices_kwargs)
        self.key = PIT_UNIVERSES["sp500"]
        self.saved = pit_universe._cache.get(self.key)
        pit_universe._cache[self.key] = _universe(self.prices, back=self.back)

    def tearDown(self):
        if self.saved is None:
            pit_universe._cache.pop(self.key, None)
        else:
            pit_universe._cache[self.key] = self.saved

    def _run(self, strategy_cls, symbols=("sp500",), pit_exit="hold", **strategy_kwargs):
        prices = self.prices
        cut = prices.copy()
        cut.loc[cut.index[OUT[0]:], "X"] = np.nan
        if self.back:
            cut.loc[cut.index[OUT[1]:], "X"] = prices.loc[prices.index[OUT[1]:], "X"].values

        def loader(*args, **kwargs):
            return (cut if kwargs.get("pit_cut", True) else prices).copy()

        with mock.patch.object(pwb_ds, "get_pricing", loader):
            return be.run_strategy(
                indicator_cls=None,
                indicator_kwargs={},
                strategy_cls=strategy_cls,
                strategy_kwargs=strategy_kwargs,
                symbols=list(symbols),
                start_date="2020-01-01",
                cash=100_000.0,
                broker_kwargs={"commission": 0.0},
                pit_exit=pit_exit,
            )

    def _px(self, symbol, field, i):
        return float(self.prices[(symbol, field)].iloc[i])

    def _last_member_close(self, strategy):
        return self._px("X", "close", int(np.argmax(strategy.pit_membership.out["X"])) - 1)

    def _x_sales_outside(self, strategy):
        flags = strategy.pit_membership.out["X"]
        return [f for f in strategy.fills if f[0] == "X" and flags[f[1]]]

    def _nav(self, strategy, i):
        return float(strategy.log_data[i]["value"])

    def assertBooksBalance(self, strategy, i):
        """NAV on bar ``i`` = start cash - what the fills cost + the settlements + holdings at the close.

        Valid once X is flat again: any mark left in the cash, or counted
        twice, shows up as a difference.
        """
        self.assertEqual(strategy.held[i].get("X", 0), 0)
        cash = 100_000.0 - sum(size * price for _, j, size, price in strategy.fills if j <= i)
        cash += sum(e["cash"] for e in strategy.membership_audit["settled"].values())
        value = cash + sum(
            size * self._px(s, "close", i) for s, size in strategy.held[i].items() if size
        )
        self.assertAlmostEqual(self._nav(strategy, i), value, delta=1e-6 * value)


class LongHeldTest(_Base):
    def test_the_books_balance_after_the_close(self):
        strategy = self._run(LongX)
        self.assertGreater(strategy.held[110]["X"], 0)
        self.assertBooksBalance(strategy, NEXT + 5)
        self.assertEqual(strategy._pwb_ms_marked, 0.0)

    def test_it_earns_the_real_move(self):
        strategy = self._run(LongX)
        size = strategy.held[110]["X"]
        sales = self._x_sales_outside(strategy)
        self.assertEqual(len(sales), 1)
        real = self._px("X", "open", sales[0][1])
        settled = strategy.membership_audit["settled"]["X"]["cash"]
        self.assertAlmostEqual(settled, size * (real - self._last_member_close(strategy)), places=6)


class ShortHeldTest(_Base):
    def test_a_short_is_marked_and_covered_at_the_real_price(self):
        strategy = self._run(ShortX)
        size = strategy.held[110]["X"]
        self.assertLess(size, 0)
        # marked through the cash while held: X rises, the short loses
        lo, hi = 112, NEXT - 1
        nav = self._nav(strategy, hi) - self._nav(strategy, lo)
        a = strategy.held[lo]["A"]
        expected = a * (self._px("A", "close", hi) - self._px("A", "close", lo))
        expected += size * (self._px("X", "close", hi - 1) - self._px("X", "close", lo - 1))
        self.assertAlmostEqual(nav, expected, places=4)
        # covered by the harness at the rebalance, settled at the real open
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)
        self.assertIn("X", strategy.membership_audit["liquidated"])
        sales = self._x_sales_outside(strategy)
        self.assertEqual([f[2] for f in sales], [-size])
        real = self._px("X", "open", sales[0][1])
        settled = strategy.membership_audit["settled"]["X"]["cash"]
        self.assertAlmostEqual(settled, size * (real - self._last_member_close(strategy)), places=6)
        self.assertLess(settled, 0)
        self.assertBooksBalance(strategy, NEXT + 5)

    def test_the_exposure_records_value_it_at_its_real_close(self):
        strategy = self._run(ShortX)
        size = strategy.held[110]["X"]
        day = self.prices.index[NEXT].date()
        records = {d: (long, short) for d, long, short in strategy._pwb_cap_records}
        value = self._nav(strategy, NEXT)
        # X is not among the bar's targets: the record carries it as held,
        # at its real close -- not at the flat line's last member close
        self.assertAlmostEqual(
            records[day][1], -size * self._px("X", "close", NEXT) / value, places=9
        )


class CollapseTest(_Base):
    """X loses 85 % after it leaves, in a fully invested book."""

    prices_kwargs = {"move": 0.15}

    def test_the_mark_is_not_read_as_a_debit(self):
        strategy = self._run(LongX)
        self.assertEqual(strategy.run_report["attempts"], 1)  # no re-run at a smaller exposure
        self.assertEqual(strategy.exposure_cap, 1.0)
        funding = strategy.analyzers.funding.get_analysis()
        self.assertGreater(funding["min_cash"], 0.0)  # 96 % invested: no debit
        self.assertBooksBalance(strategy, NEXT + 5)


class CheatOnCloseTest(_Base):
    def test_a_coc_sale_is_settled_at_the_real_close_of_its_bar(self):
        strategy = self._run(LongX, coc=True)
        size = strategy.held[110]["X"]
        sales = [f for f in strategy.fills if f[0] == "X" and f[2] < 0 and f[1] < OUT[1]]
        self.assertEqual(len(sales), 1)
        placed = sales[0][1] - 1  # filled on the next bar, at the close of this one
        self.assertEqual(placed, NEXT)
        settled = strategy.membership_audit["settled"]["X"]["cash"]
        real = self._px("X", "close", placed)
        self.assertAlmostEqual(settled, size * (real - self._last_member_close(strategy)), places=6)
        self.assertBooksBalance(strategy, NEXT + 5)


class DelistedWhileHeldTest(_Base):
    """X leaves the universe for good and stops printing on bar 110."""

    prices_kwargs = {"last_print": 110}
    back = False

    def test_it_is_sold_at_its_last_close(self):
        strategy = self._run(LongX)
        size = strategy.held[110]["X"]
        self.assertGreater(size, 0)
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)
        settled = strategy.membership_audit["settled"]["X"]["cash"]
        last = self._px("X", "close", 110)
        self.assertAlmostEqual(settled, size * (last - self._last_member_close(strategy)), places=6)
        self.assertBooksBalance(strategy, NEXT + 5)


class HedgeOrdersTest(_Base):
    prices_kwargs = {"hedge": True}

    def test_a_daily_order_on_a_listed_hedge_is_not_a_rebalance(self):
        strategy = self._run(LongXWithDailyHedge, symbols=("sp500", "H"))
        self.assertGreater(strategy.held[NEXT - 1]["X"], 0)  # held to the rebalance
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)


class HarnessCloseFundsThePurchasesTest(_Base):
    def test_the_close_is_checked_before_the_purchases(self):
        strategy = self._run(TargetsOnlyTheMembers)
        self.assertIn("X", strategy.membership_audit["liquidated"])
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)
        self.assertEqual([r for r in strategy.rejected if r[2] == "Margin"], [])
        self.assertGreater(strategy.held[NEXT + 2]["A"], strategy.held[NEXT - 1]["A"])
        self.assertEqual(strategy.run_report["attempts"], 1)


class EngineIndependentTest(_Base):
    def test_liquidate_ignores_the_new_accounts(self):
        strategy = self._run(LongX, pit_exit="liquidate")
        self.assertEqual(strategy.membership_audit["settled"], {})
        self.assertEqual(strategy._pwb_ms_marked, 0.0)
        self.assertEqual(strategy.held[110]["X"], 0)


if __name__ == "__main__":
    unittest.main()
