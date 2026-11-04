"""A name that leaves the point-in-time universe is held to the next rebalance, at its real prices.

The papers form a portfolio among the members of the formation date and hold
it to the next rebalance at the prices the names actually trade at, whether
they stay in the universe or not. 0.1.43 instead closed the position on the
first bar outside, at the last member close, and refused every order until
the name came back: a monthly book became a book rebalanced every time one of
its names crossed rank 500, and a screen that kept choosing a non-member sat
in cash. ``pit_exit="hold"`` keeps the real prices, refuses only the orders
that open or add to a position in a non-member, and closes what the strategy
still holds there on its next rebalancing bar. These scenarios fail on 0.1.43.
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
OUT = (105, 200)  # bars during which X is not a member: it leaves mid-period
EVERY = 20  # the strategies below rebalance on bars 0, 20, 40, ... (len % 20 == 1)
NEXT = 120  # the first rebalancing bar after X leaves


def _prices():
    """X trades all along; it rises 30 % in the weeks after it leaves, then holds that level."""
    rng = np.random.default_rng(5)
    a = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    b = 100 * np.exp(np.cumsum(rng.normal(0, 0.010, N)))
    x = 50 * np.exp(np.cumsum(rng.normal(0, 0.002, N)))
    ramp = np.ones(N)
    ramp[OUT[0]:NEXT + 5] = np.linspace(1.0, 1.3, NEXT + 5 - OUT[0])
    ramp[NEXT + 5:] = 1.3
    return panel({"A": a, "B": b, "X": x * ramp})


def _universe(prices):
    rows = []
    for i, day in enumerate(prices.index):
        for rank, symbol in enumerate(("A", "B", "X"), start=1):
            if symbol == "X" and OUT[0] <= i < OUT[1]:
                continue
            rows.append((day, symbol, rank))
    return pd.DataFrame(rows, columns=["date", "symbol", "rank"])


def _first_out(strategy):
    """The first bar X spends outside, as the run saw it."""
    return int(np.argmax(strategy.pit_membership.out["X"]))


class _Recorder(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.rejected = []
        self.held = {}
        self.member = {}
        self.fills = []

    def notify_order(self, order):
        day = self.datas[0].datetime.date(0)
        if order.status == order.Rejected:
            self.rejected.append((order.data._name, day, order.isbuy()))
        if order.status == order.Completed:
            self.fills.append((order.data._name, day, order.executed.size, order.executed.price))

    def next(self):
        super().next()
        self.held[len(self) - 1] = {d._name: self.getposition(d).size for d in self.datas}
        member = getattr(self, "is_member", lambda d: True)  # 0.1.43 has none
        self.member[len(self) - 1] = {d._name: member(d) for d in self.datas}
        if len(self) % EVERY == 1:
            self.rebalance()


class EqualWeightOfMembers(_Recorder):
    """Every 20 bars, equal weight on the names ``is_tradable`` lets through."""

    def rebalance(self):
        names = [d for d in self.datas if self.is_tradable(d)]
        for d in self.datas:
            if d not in names:
                self.order_target_percent(d, 0.0)
        for d in names:
            self.order_target_percent(d, 0.95 / len(names))


class AlwaysX(_Recorder):
    """Every 20 bars, all-in on X, whatever the universe says (a screen that ignores it)."""

    def rebalance(self):
        for d in self.datas:
            if d._name != "X":
                self.order_target_percent(d, 0.0)
        self.order_target_percent(self.getdatabyname("X"), 0.95)


class FlatLineScreen(_Recorder):
    """Every 20 bars, equal weight on the names whose close moved -- its own filter, not is_tradable.

    The idiom of 439 published "sp500" strategies: a non-member's bars are a
    flat line, so this screen never selects one as long as the feed stays flat.
    """

    def rebalance(self):
        live = [d for d in self.datas if d.close[0] != d.close[-1] or d.close[-1] != d.close[-2]]
        for d in self.datas:
            if d not in live:
                self.order_target_percent(d, 0.0)
        for d in live:
            self.order_target_percent(d, 0.95 / len(live))


class HalveXOnBar110(_Recorder):
    """Buys X on bar 100, sells half of it on bar 110 (outside), tries to buy some on bar 115.

    The sale makes bar 110 a rebalancing bar: the harness closes what is left.
    """

    def next(self):
        _Recorder.next(self)
        i = len(self) - 1
        x = self.getdatabyname("X")
        if i == 100:
            self.order_target_percent(x, 0.5)
        elif i == 110:
            self.sell(x, size=self.getposition(x).size // 2)
        elif i == 115:
            self.buy(x, size=10)

    def rebalance(self):
        pass


class _Base(unittest.TestCase):
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

    def _run(self, strategy_cls, pit_exit="hold", calls=None):
        prices = self.prices
        cut = prices.copy()
        cut.loc[cut.index[OUT[0]:OUT[1]], "X"] = np.nan  # what apply_pit_membership leaves

        def loader(*args, **kwargs):
            if calls is not None:
                calls.append(kwargs)
            return (cut if kwargs.get("pit_cut", True) else prices).copy()

        from unittest import mock
        import pwb_toolbox.datasets as pwb_ds

        with mock.patch.object(pwb_ds, "get_pricing", loader):
            return be.run_strategy(
                indicator_cls=None,
                indicator_kwargs={},
                strategy_cls=strategy_cls,
                strategy_kwargs={},
                symbols=["sp500"],
                start_date="2020-01-01",
                cash=100_000.0,
                broker_kwargs={"commission": 0.0},
                **({} if pit_exit is None else {"pit_exit": pit_exit}),
            )

    def _x(self, field, i):
        return float(self.prices[("X", field)].iloc[i])

    def _nav(self, strategy):
        return pd.Series(
            [row["value"] for row in strategy.log_data],
            index=pd.to_datetime([row["date"] for row in strategy.log_data]),
        )


class HoldToRebalanceTest(_Base):
    def test_the_panel_is_loaded_uncut(self):
        calls = []
        self._run(EqualWeightOfMembers, calls=calls)
        self.assertTrue(calls)
        self.assertIs(calls[0].get("pit_cut"), False)

    def test_it_is_held_through_the_exit_until_the_next_rebalance(self):
        strategy = self._run(EqualWeightOfMembers)
        self.assertGreater(strategy.held[OUT[0] - 1]["X"], 0)
        self.assertGreater(strategy.held[OUT[0] + 10]["X"], 0)  # 0.1.43: sold at the exit
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)

    def test_its_sale_is_settled_at_the_real_price(self):
        strategy = self._run(EqualWeightOfMembers)
        out = self.prices.index[OUT[0]].date()
        back = self.prices.index[OUT[1]].date()
        sells = [f for f in strategy.fills if f[0] == "X" and f[2] < 0 and out <= f[1] < back]
        self.assertEqual(len(sells), 1)
        _, day, size, price = sells[0]
        self.assertEqual(day, self.prices.index[NEXT + 1].date())
        # the broker fills on the flat line, at the last member close (the
        # membership's 7-day as-of tolerance keeps a few bars after OUT[0]) ...
        last = self._x("close", _first_out(strategy) - 1)
        self.assertAlmostEqual(price, last, places=9)
        # ... and the harness pays the difference with the real open
        real = self._x("open", NEXT + 1)
        self.assertGreater(real, last * 1.05)
        settled = strategy.membership_audit["settled"]["X"]
        self.assertEqual(settled["fills"], 1)
        self.assertAlmostEqual(settled["cash"], -size * (real - last), places=6)

    def test_it_is_marked_to_its_real_close_while_held_outside(self):
        strategy = self._run(EqualWeightOfMembers)
        nav = self._nav(strategy)
        days = self.prices.index
        lo, hi = _first_out(strategy) + 2, NEXT - 1  # nothing trades in between
        held = strategy.held[lo]

        def close(s, i):
            return float(self.prices[(s, "close")].iloc[i])

        # A and B on the feed; X through the cash, one bar late
        expected = sum(held[s] * (close(s, hi) - close(s, lo)) for s in ("A", "B"))
        expected += held["X"] * (close("X", hi - 1) - close("X", lo - 1))
        self.assertAlmostEqual(nav.loc[days[hi]] - nav.loc[days[lo]], expected, places=4)
        self.assertGreater(held["X"] * (close("X", hi - 1) - close("X", lo - 1)), 1000)

    def test_the_book_earns_the_real_return_of_the_name(self):
        hold = self._nav(self._run(EqualWeightOfMembers))
        liquidate = self._nav(self._run(EqualWeightOfMembers, pit_exit="liquidate"))
        after = self.prices.index[NEXT + 3]
        # X rose about 30 % between its exit and the rebalance; liquidate sold it at the exit
        self.assertGreater(hold.loc[after] - liquidate.loc[after], 0.05 * 0.95 / 3 * 100_000)

    def test_is_member_and_is_tradable_say_no_while_it_is_outside(self):
        strategy = self._run(EqualWeightOfMembers)
        self.assertTrue(strategy.member[OUT[0] - 1]["X"])
        self.assertFalse(strategy.member[OUT[0] + 10]["X"])
        self.assertTrue(strategy.member[OUT[1] + 1]["X"])
        self.assertTrue(all(strategy.member[i]["A"] for i in strategy.member))
        # the screen formed among the members: no order on X was ever refused
        self.assertFalse([r for r in strategy.rejected if r[0] == "X"])

    def test_it_is_bought_back_when_it_returns(self):
        strategy = self._run(EqualWeightOfMembers)
        first_back = (OUT[1] // EVERY + 1) * EVERY
        self.assertGreater(strategy.held[first_back + 2]["X"], 0)

    def test_the_report_counts_the_close(self):
        strategy = self._run(EqualWeightOfMembers)
        self.assertEqual(strategy.run_report["membership"]["pit_exit"], "hold")
        # the strategy closed X itself at its rebalance: nothing for the harness to do
        self.assertEqual(strategy.membership_audit["liquidated"], {})


class StrategyThatKeepsChoosingItTest(_Base):
    def test_the_harness_closes_it_at_the_next_rebalance(self):
        strategy = self._run(AlwaysX)
        self.assertGreater(strategy.held[OUT[0] + 10]["X"], 0)
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)
        closed = strategy.membership_audit["liquidated"]["X"]
        self.assertEqual(closed["first"], self.prices.index[NEXT].date())
        self.assertAlmostEqual(closed["prices"][0], self._x("close", _first_out(strategy) - 1), places=9)
        # the harness's close, and the strategy's own trim when there is one
        self.assertGreaterEqual(strategy.membership_audit["settled"]["X"]["fills"], 1)

    def test_new_buys_are_refused_until_it_returns(self):
        strategy = self._run(AlwaysX)
        refused = [day for name, day, _ in strategy.rejected if name == "X"]
        self.assertTrue(refused)
        days = self.prices.index
        self.assertTrue(all(days[NEXT].date() < d < days[OUT[1]].date() for d in refused))
        self.assertEqual(strategy.held[OUT[1] - 1]["X"], 0)
        self.assertGreater(strategy.held[(OUT[1] // EVERY + 1) * EVERY + 2]["X"], 0)


class FlatLineScreenTest(_Base):
    def test_a_screen_on_flat_lines_never_picks_a_non_member(self):
        strategy = self._run(FlatLineScreen)
        self.assertFalse([r for r in strategy.rejected if r[0] == "X"])
        self.assertEqual(strategy.held[OUT[1] - 1]["X"], 0)
        self.assertGreater(strategy.held[OUT[0] + 10]["X"], 0)  # held to the next rebalance


class ReductionsPassTest(_Base):
    def test_a_sale_outside_passes_and_a_purchase_does_not(self):
        strategy = self._run(HalveXOnBar110)
        before = strategy.held[109]["X"]
        self.assertGreater(before, 0)
        sells = [f for f in strategy.fills if f[0] == "X" and f[2] < 0]
        # the strategy's half, then the harness's rest -- never more than was held
        self.assertEqual(sorted(-f[2] for f in sells), sorted([before // 2, before - before // 2]))
        self.assertEqual(strategy.held[112]["X"], 0)
        self.assertEqual(strategy.held[117]["X"], 0)
        self.assertEqual(
            [(n, buy) for n, _, buy in strategy.rejected], [("X", True)]
        )


class DefaultTest(_Base):
    def test_hold_is_the_default(self):
        strategy = self._run(EqualWeightOfMembers, pit_exit=None)
        self.assertGreater(strategy.held[OUT[0] + 10]["X"], 0)  # 0.1.43: sold at the exit
        self.assertEqual(strategy.held[NEXT + 2]["X"], 0)


class NeverAMemberTest(_Base):
    def test_a_name_with_prices_but_no_membership_has_no_feed(self):
        # Z was a member on bars 0-19, when it has no price; it prints from bar 50 on
        rng = np.random.default_rng(11)
        close = 30 * np.exp(np.cumsum(rng.normal(0, 0.01, N)))
        close[:50] = np.nan
        self.prices = pd.concat([self.prices, panel({"Z": close})], axis=1)
        table = pit_universe._cache[self.key]
        extra = pd.DataFrame({"date": self.prices.index[:20], "symbol": "Z", "rank": 4})
        pit_universe._cache[self.key] = pd.concat([table, extra]).sort_values(["date", "rank"])
        strategy = self._run(EqualWeightOfMembers)
        self.assertNotIn("Z", [d._name for d in strategy.datas])
        self.assertTrue(np.isfinite(strategy.log_data[-1]["value"]))


class LiquidateIsStillThereTest(_Base):
    def test_liquidate_sells_at_the_exit(self):
        strategy = self._run(EqualWeightOfMembers, pit_exit="liquidate")
        self.assertEqual(strategy.held[OUT[0] + 10]["X"], 0)
        self.assertIn("X", strategy.membership_audit["liquidated"])

    def test_an_unknown_policy_is_refused(self):
        with self.assertRaises(ValueError):
            self._run(EqualWeightOfMembers, pit_exit="drop")


class BuyXOnBar100(_Recorder):
    def next(self):
        _Recorder.next(self)
        if len(self) == 101:
            self.order_target_percent(self.getdatabyname("X"), 0.5)

    def rebalance(self):
        pass


class LongAbsenceTest(unittest.TestCase):
    """Three calendar years outside the universe are not a reused ticker.

    The era cut keeps only what follows a symbol's last hole of three full
    calendar years, because such a hole usually means the ticker changed
    hands. On a panel cut to the membership, a name that left the top 500 for
    three years has exactly that hole, and lost its whole earlier membership:
    299 era cuts on the "sp500" panel against 75 on the uncut one
    (the_implied_cost_of_capital, 2026-11-04).
    """

    N, OUT = 1200, (250, 1050)  # out through 2021, 2022 and 2023

    def setUp(self):
        rng = np.random.default_rng(9)
        series = {s: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, self.N))) for s in ("A", "X")}
        self.prices = panel(series)
        rows = [
            (day, s, r)
            for i, day in enumerate(self.prices.index)
            for r, s in enumerate(("A", "X"), start=1)
            if not (s == "X" and self.OUT[0] <= i < self.OUT[1])
        ]
        self.key = PIT_UNIVERSES["sp500"]
        self.saved = pit_universe._cache.get(self.key)
        pit_universe._cache[self.key] = pd.DataFrame(rows, columns=["date", "symbol", "rank"])

    def tearDown(self):
        if self.saved is None:
            pit_universe._cache.pop(self.key, None)
        else:
            pit_universe._cache[self.key] = self.saved

    def _run(self, pit_exit):
        full = self.prices
        cut = full.copy()
        cut.loc[cut.index[self.OUT[0]:self.OUT[1]], "X"] = np.nan
        from unittest import mock
        import pwb_toolbox.datasets as pwb_ds

        loader = lambda *a, **k: (cut if k.get("pit_cut", True) else full).copy()
        with mock.patch.object(pwb_ds, "get_pricing", loader):
            return be.run_strategy(
                indicator_cls=None, indicator_kwargs={}, strategy_cls=BuyXOnBar100,
                strategy_kwargs={}, symbols=["sp500"], start_date="2020-01-01",
                cash=100_000.0, broker_kwargs={"commission": 0.0}, pit_exit=pit_exit,
            )

    def test_hold_keeps_the_earlier_membership(self):
        strategy = self._run("hold")
        self.assertGreater(strategy.held[105]["X"], 0)
        self.assertEqual(strategy.listing_audit, {})

    def test_liquidate_loses_it_to_the_era_cut(self):
        strategy = self._run("liquidate")
        self.assertEqual(strategy.held[105]["X"], 0)
        self.assertIn("X", strategy.listing_audit)


class ToleranceMaskTest(unittest.TestCase):
    def test_the_tolerant_mask_is_the_rows_the_cut_keeps(self):
        days = pd.bdate_range("2021-01-04", periods=60)
        member_days = [d for i, d in enumerate(days) if i < 20 or 40 <= i < 50]
        table = pd.DataFrame({"date": member_days, "symbol": "Y", "rank": 1})
        table = pd.concat([table, pd.DataFrame({"date": days, "symbol": "W", "rank": 2})])
        table = table.sort_values(["date", "rank"])  # as load_pit_universe returns it
        key = (9, 0)
        pit_universe._cache[key] = table
        try:
            long = pd.DataFrame({"date": list(days) * 2, "symbol": ["Y"] * 60 + ["W"] * 60, "close": 1.0})
            kept = pit_universe.apply_pit_membership(long, *key)
            mask = pit_universe.membership_mask(
                days, ["Y", "W"], *key, tolerance=pit_universe._ASOF_TOLERANCE
            )
        finally:
            pit_universe._cache.pop(key, None)
        for symbol in ("Y", "W"):
            rows = set(pd.to_datetime(kept.loc[kept["symbol"] == symbol, "date"]))
            self.assertEqual(rows, set(mask.index[mask[symbol]]), symbol)


if __name__ == "__main__":
    unittest.main()
