"""A name that leaves the point-in-time universe is sold, not frozen.

``apply_pit_membership`` drops the rows of a name outside its membership and
``run_strategy`` used to forward-fill the hole: the name kept a flat price
(volatility and beta of zero), sorted to the top of every low-volatility
screen, was held through its absence, and the whole move it made while away
landed on the book in one bar when it came back (CIT on 2009-12-10, 0.7 to
29 dollars). These scenarios fail on 0.1.42.
"""

import unittest

import numpy as np
import pandas as pd

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.datasets import PIT_UNIVERSES
from pwb_toolbox.datasets import pit_universe

from _synthetic import offline, panel

N = 300
OUT = (100, 200)  # bars during which X is not a member


def _prices():
    rng = np.random.default_rng(3)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    b = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    # X is the quiet name -- until it leaves the universe and comes back 60 % higher
    x = 50 * np.exp(np.cumsum(rng.normal(0, 0.002, N)))
    x[OUT[1]:] *= 1.6
    x[OUT[0]:OUT[1]] = np.nan
    return panel({"A": a, "B": b, "X": x})


def _universe(prices):
    """Membership as the published table carries it: one row per member and session."""
    rows = []
    for i, day in enumerate(prices.index):
        for rank, symbol in enumerate(("A", "B", "X"), start=1):
            if symbol == "X" and OUT[0] <= i < OUT[1]:
                continue
            rows.append((day, symbol, rank))
    return pd.DataFrame(rows, columns=["date", "symbol", "rank"])


class LowVolatility(BaseStrategy):
    """Every 20 bars, all-in on the name with the lowest 20-bar volatility."""

    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.rejected = []
        self.held = {}

    def notify_order(self, order):
        if order.status == order.Rejected:
            self.rejected.append((order.data._name, self.datas[0].datetime.date(0)))

    def next(self):
        super().next()
        self.held[len(self)] = {d._name: self.getposition(d).size for d in self.datas}
        if len(self) < 21 or len(self) % 20 != 1:
            return
        vols = {}
        for d in self.datas:
            closes = np.array(d.close.get(size=21))
            vols[d._name] = np.std(np.diff(np.log(closes)))
        pick = min(vols, key=vols.get)
        for d in self.datas:
            if d._name != pick:
                self.order_target_percent(d, 0.0)
        self.order_target_percent(self.getdatabyname(pick), 0.95)


class PitExitTest(unittest.TestCase):
    def setUp(self):
        self.prices = _prices()
        self.key = PIT_UNIVERSES["sp500"]
        self.saved = pit_universe._cache.get(self.key)
        pit_universe._cache[self.key] = _universe(self.prices)

    def tearDown(self):
        if self.saved is None:
            pit_universe._cache.pop(self.key, None)
        else:
            pit_universe._cache[self.key] = self.saved

    def _run(self):
        with offline(self.prices):
            return be.run_strategy(
                indicator_cls=None,
                indicator_kwargs={},
                strategy_cls=LowVolatility,
                strategy_kwargs={},
                symbols=["sp500"],
                start_date="2020-01-01",
                cash=100_000.0,
                broker_kwargs={"commission": 0.0},
            )

    def test_the_quiet_name_is_held_before_it_leaves(self):
        strategy = self._run()
        self.assertGreater(strategy.held[90]["X"], 0)

    def test_it_is_sold_when_it_leaves(self):
        strategy = self._run()
        # the 7-day as-of tolerance of the membership keeps it a few sessions
        self.assertEqual(strategy.held[OUT[0] + 10]["X"], 0)
        self.assertEqual(strategy.held[OUT[1] - 1]["X"], 0)
        self.assertIn("X", strategy.membership_audit["liquidated"])

    def test_orders_on_it_are_refused_while_it_is_out(self):
        strategy = self._run()
        refused = [day for name, day in strategy.rejected if name == "X"]
        self.assertTrue(refused)
        self.assertTrue(all(
            self.prices.index[OUT[0]].date() <= day < self.prices.index[OUT[1]].date()
            for day in refused
        ))
        self.assertGreater(strategy.membership_audit["refused"]["X"]["orders"], 0)

    def test_its_return_while_away_never_reaches_the_book(self):
        strategy = self._run()
        nav = pd.Series(
            [row["value"] for row in strategy.log_data],
            index=pd.to_datetime([row["date"] for row in strategy.log_data]),
        )
        back = self.prices.index[OUT[1]]
        # 0.1.42: +57 % in one bar, X held flat through its absence
        self.assertLess(abs(nav.loc[back] / nav.shift(1).loc[back] - 1), 0.05)

    def test_it_is_sold_at_its_last_price(self):
        strategy = self._run()
        last = self.prices[("X", "close")].iloc[OUT[0] - 1]
        fills = strategy.membership_audit["liquidated"]["X"]["prices"]
        self.assertTrue(fills)
        for price in fills:
            self.assertAlmostEqual(price, last, places=9)


class MembershipMaskTest(unittest.TestCase):
    def test_membership_is_read_on_the_last_session(self):
        days = pd.bdate_range("2021-01-04", periods=30)
        sessions = days.delete(25)  # a market holiday: no row for anyone
        table = pd.concat([
            pd.DataFrame({"date": sessions, "symbol": "W", "rank": 1}),
            pd.DataFrame({
                "date": [d for i, d in enumerate(days) if (i < 10 or i >= 20) and i != 25],
                "symbol": "Y",
                "rank": 2,
            }),
        ])
        key = (7, 0)
        pit_universe._cache[key] = table
        try:
            mask = pit_universe.membership_mask(days, ["Y", "Z"], *key)
        finally:
            pit_universe._cache.pop(key, None)
        member = mask["Y"].to_numpy()
        self.assertTrue(member[:10].all())
        self.assertFalse(member[10:20].any())
        self.assertTrue(member[20:].all())  # the holiday carries the last session
        self.assertFalse(mask["Z"].any())


if __name__ == "__main__":
    unittest.main()
