"""A name held after it leaves the universe moves the NAV on the day it moves in the market.

``pit_exit="hold"`` keeps the feed flat outside the universe (screens that skip
flat lines must not see a non-member move) and books the difference with the
real close through the cash. Before 0.1.54 that cash was booked after the
strategy's ``next`` and landed one bar later: on ``predicting_anomalies`` the
probe saw QUBT held short at 7.85 every day of June 2025 while it traded
14-21, and the NAV followed its real moves a day late. The mark now lands
before ``next``: the NAV the bar records, the value the strategy sizes on and
the analyzers carry the real close of the bar itself, every bar until the sale.
"""

import unittest

import numpy as np

from test_pit_hold_accounting import (
    NEXT,
    OUT,
    BuyAndHold,
    ShortX,
    _Base,
    _Recorder,
)


class _SeesValue(_Recorder):
    """Records ``broker.getvalue()`` as the strategy reads it inside ``next``."""

    def __init__(self):
        super().__init__()
        self.seen = {}

    def next(self):
        self.seen[len(self) - 1] = self.broker.getvalue()
        super().next()


class ShortXSees(_SeesValue, ShortX):
    pass


class HoldThroughReturn(_Base):
    """Bought on bar 100 and never traded: X is held through its exit and its return."""

    def test_every_bar_outside_moves_with_the_real_close(self):
        strategy = self._run(BuyAndHold)
        first = int(np.argmax(strategy.pit_membership.out["X"]))
        held = strategy.held[first]
        self.assertGreater(held["X"], 0)
        for i in range(first, OUT[1] + 3):
            got = self._nav(strategy, i) - self._nav(strategy, i - 1)
            want = sum(
                size * (self._px(s, "close", i) - self._px(s, "close", i - 1))
                for s, size in held.items()
                if size
            )
            self.assertAlmostEqual(got, want, places=4, msg=f"bar {i}")

    def test_no_catch_up_on_the_bar_it_comes_back(self):
        strategy = self._run(BuyAndHold)
        back = OUT[1]
        self.assertFalse(strategy.pit_membership.out["X"][back])
        nav = np.array([row["value"] for row in strategy.log_data])
        jumps = np.abs(np.diff(np.log(nav[100:])))
        self.assertLess(jumps.max(), 0.05)  # X moves ~0.2 % a day; a catch-up would not


class ShortHeldOutside(_Base):
    def test_the_short_moves_the_nav_on_the_same_bar(self):
        strategy = self._run(ShortXSees)
        size = strategy.held[110]["X"]
        a = strategy.held[110]["A"]
        self.assertLess(size, 0)
        for i in range(112, NEXT):
            got = self._nav(strategy, i) - self._nav(strategy, i - 1)
            want = a * (self._px("A", "close", i) - self._px("A", "close", i - 1))
            want += size * (self._px("X", "close", i) - self._px("X", "close", i - 1))
            self.assertAlmostEqual(got, want, places=4, msg=f"bar {i}")

    def test_the_strategy_sizes_on_the_marked_value(self):
        strategy = self._run(ShortXSees)
        for i in range(112, NEXT):
            self.assertAlmostEqual(strategy.seen[i], self._nav(strategy, i), places=6)

    def test_the_mark_is_still_not_read_as_a_debit(self):
        strategy = self._run(ShortXSees)
        audit = strategy.funding_audit
        self.assertGreater(audit["min_cash"], 0)


if __name__ == "__main__":
    unittest.main()
