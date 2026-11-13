"""A holiday is not a bar, and a filled bar is flat at the previous close.

``run_strategy`` reindexed the panel on ``bdate_range`` and forward-filled it:
every weekday without a session (New Year's Day, Thanksgiving...) became a
copy of the day before, its open included. backtrader fills an order at the
open of the next bar, so an order sent at the close of the eve of a holiday
filled at the *open of that same eve* -- a price older than the signal.
Both scenarios below fail on 0.1.50.
"""

import unittest

import numpy as np
import pandas as pd

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be

from _synthetic import offline, panel

EVE = pd.Timestamp("2020-12-31")
HOLIDAY = pd.Timestamp("2021-01-01")  # a Friday: a weekday without a session
NEXT = pd.Timestamp("2021-01-04")


def _drop_rows(prices: pd.DataFrame, days) -> pd.DataFrame:
    """The panel ``get_pricing`` returns: no row at all on a day nothing traded."""
    return prices.drop(index=pd.DatetimeIndex(days))


def _with_opens(closes: dict, start: str) -> pd.DataFrame:
    """Opens half a point under the close, so no open equals any close."""
    opens = {s: np.asarray(c, dtype=float) - 0.5 for s, c in closes.items()}
    return panel(closes, start=start, opens=opens)


class BuyOnce(BaseStrategy):
    """Buys 10 shares of the first feed at the close of ``on``; records every bar."""

    params = (("indicator_cls", None), ("indicator_kwargs", {}), ("on", None))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.bars = {}
        self.fills = []

    def notify_order(self, order):
        if order.status == order.Completed:
            self.fills.append(
                (order.data._name, order.data.datetime.date(0), order.executed.price)
            )

    def next(self):
        super().next()
        today = pd.Timestamp(self.datas[0].datetime.date(0))
        self.bars[today] = {
            d._name: (d.open[0], d.high[0], d.low[0], d.close[0]) for d in self.datas
        }
        if today == self.p.on:
            self.buy(data=self.datas[0], size=10)


def _run(prices, on):
    with offline(prices):
        return be.run_strategy(
            indicator_cls=None,
            indicator_kwargs={},
            strategy_cls=BuyOnce,
            strategy_kwargs={"on": on},
            symbols=list(prices.columns.get_level_values(0).unique()),
            start_date="2020-12-01",
            cash=100_000.0,
            broker_kwargs={"commission": 0.0},
        )


class UsHolidayTest(unittest.TestCase):
    def setUp(self):
        n = 40
        closes = {
            "AAA": 100 + np.arange(n, dtype=float),
            "BBB": 50 + 0.5 * np.arange(n, dtype=float),
        }
        self.prices = _drop_rows(
            _with_opens(closes, "2020-12-01"), ["2020-12-25", HOLIDAY]
        )

    def test_the_holiday_is_not_a_bar(self):
        strategy = _run(self.prices, EVE)
        self.assertNotIn(HOLIDAY, strategy.bars)
        self.assertNotIn(pd.Timestamp("2020-12-25"), strategy.bars)
        self.assertIn(EVE, strategy.bars)
        self.assertIn(NEXT, strategy.bars)

    def test_an_order_at_the_eve_fills_at_the_next_session_open(self):
        strategy = _run(self.prices, EVE)
        self.assertEqual(len(strategy.fills), 1)
        name, day, price = strategy.fills[0]
        self.assertEqual(name, "AAA")
        self.assertEqual(pd.Timestamp(day), NEXT)
        self.assertAlmostEqual(price, self.prices.loc[NEXT, ("AAA", "open")])
        # not the open of the eve, a price older than the close it was sent on
        self.assertNotAlmostEqual(price, self.prices.loc[EVE, ("AAA", "open")])

    def test_a_panel_with_an_empty_row_on_the_holiday_is_the_same(self):
        # a loader that keeps the row, every close NaN, gives the same run
        empty = self.prices.reindex(self.prices.index.union([HOLIDAY]))
        strategy = _run(empty, EVE)
        self.assertNotIn(HOLIDAY, strategy.bars)
        self.assertEqual(pd.Timestamp(strategy.fills[0][1]), NEXT)


class MixedPanelTest(unittest.TestCase):
    """A US name and a London name, on a day only London traded: the session stays."""

    US_OFF = pd.Timestamp("2020-12-16")  # London trades, the US name does not
    EVE = pd.Timestamp("2020-12-15")

    def setUp(self):
        n = 40
        closes = {
            "USX": 100 + np.arange(n, dtype=float),
            "LSE": 200 + np.arange(n, dtype=float),
            # listed mid-panel: its leading gap is the back-fill's, unchanged
            "NEW": np.r_[np.full(10, np.nan), 300 + np.arange(n - 10, dtype=float)],
        }
        prices = _with_opens(closes, "2020-12-01")
        prices.loc[self.US_OFF, ["USX", "NEW"]] = np.nan
        self.prices = prices

    def test_the_filled_cell_is_flat_at_the_previous_close(self):
        strategy = _run(self.prices, self.EVE)
        self.assertIn(self.US_OFF, strategy.bars)  # London traded: a session
        previous_close = self.prices.loc[self.EVE, ("USX", "close")]
        self.assertEqual(strategy.bars[self.US_OFF]["USX"], (previous_close,) * 4)
        # London's real bar is untouched
        real = tuple(self.prices.loc[self.US_OFF, "LSE"][["open", "high", "low", "close"]])
        self.assertEqual(strategy.bars[self.US_OFF]["LSE"], real)

    def test_an_order_filled_on_it_gets_the_previous_close(self):
        strategy = _run(self.prices, self.EVE)
        name, day, price = strategy.fills[0]
        self.assertEqual((name, pd.Timestamp(day)), ("USX", self.US_OFF))
        self.assertAlmostEqual(price, self.prices.loc[self.EVE, ("USX", "close")])
        self.assertNotAlmostEqual(price, self.prices.loc[self.EVE, ("USX", "open")])

    def test_the_leading_back_fill_is_unchanged(self):
        strategy = _run(self.prices, self.EVE)
        first = self.prices["NEW"].dropna().iloc[0]
        lead = strategy.bars[self.prices.index[0]]["NEW"]
        self.assertEqual(lead, tuple(first[["open", "high", "low", "close"]]))


class WeekendTest(unittest.TestCase):
    def test_weekend_bars_stay_out(self):
        # a crypto panel has a row every calendar day; the weekdays are the bars, as before
        days = pd.date_range("2020-12-01", periods=40, freq="D")
        closes = 100 + np.arange(len(days), dtype=float)
        frame = pd.DataFrame(
            {"open": closes - 0.5, "high": closes, "low": closes - 0.5, "close": closes},
            index=days,
        )
        prices = pd.concat({"BTC": frame}, axis=1)
        prices.columns.names = [None, None]
        strategy = _run(prices, None)
        bars = pd.DatetimeIndex(sorted(strategy.bars))
        self.assertTrue((bars.dayofweek < 5).all())
        self.assertEqual(len(bars), int((days.dayofweek < 5).sum()))


if __name__ == "__main__":
    unittest.main()
