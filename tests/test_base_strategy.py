"""Tests for `pwb_toolbox.backtesting.base_strategy`.

`is_tradable` only ever touches `data.close`, so the cases below drive it with
a stub line rather than standing up a Cerebro run: the method is called unbound
with `self=None`.
"""

from pwb_toolbox.backtesting.base_strategy import BaseStrategy


class FakeLine:
    """Stand-in for a backtrader line.

    Index 0 is the current bar and negative indices step backwards into
    history, matching backtrader's convention.
    """

    def __init__(self, values):
        self._values = list(values)  # oldest first; the last entry is bar 0

    def __len__(self):
        return len(self._values)

    def __getitem__(self, ago):
        return self._values[len(self._values) - 1 + ago]


class FakeData:
    def __init__(self, closes):
        self.close = FakeLine(closes)


def is_tradable(closes):
    return BaseStrategy.is_tradable(None, FakeData(closes))


def test_moving_price_is_tradable():
    assert is_tradable([100.0, 100.0, 101.0]) is True


def test_flat_latest_bar_is_not_tradable():
    """The previous bar is the one that matters.

    Before the fix the comparison reached back to `close[-2]`, so a feed whose
    price stalled on the latest bar but moved before that was still reported
    tradable.
    """
    assert is_tradable([99.0, 100.0, 100.0]) is False


def test_two_bars_are_enough_to_decide():
    """The length guard only needs the current bar and its predecessor; it
    previously required three and so discarded the second bar of every feed."""
    assert is_tradable([100.0, 101.0]) is True
    assert is_tradable([100.0, 100.0]) is False


def test_single_bar_has_no_predecessor_to_compare():
    assert is_tradable([100.0]) is False
