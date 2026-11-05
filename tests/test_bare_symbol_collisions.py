"""A ticker that both the ETF feed and the stock feed carry resolves to the right one.

The index republished on 2026-11-02 lists 1 459 tickers under both
``ETFs-Daily-Price`` and ``Stocks-Daily-Price``, and the ETF-first priority
sent every one of them to the ETF feed. The synthetic tables below mirror the
three shapes that matter:

* ``META`` -- a stock quoted for years, and an ETF that lived a few months
  under the same ticker. The stock is what a strategy, and the point-in-time
  universe, mean.
* ``HYG`` -- the opposite: a live ETF, and a stock that carried the ticker a
  few sessions before it. The ETF is what a strategy means.
* ``SAME`` -- one fund that both feeds carry, with identical closes: the
  priority keeps the ETF feed, and nothing is worth a warning.
* ``LEV`` -- one fund again, but the stock feed's copy is not adjusted for a
  1:10 reverse split and runs two sessions longer. Still one instrument: the
  ETF feed's adjusted copy stays, though the other has more sessions.
* ``CEF`` -- one closed-end fund again, but the ETF feed only carries its
  last sixty sessions. The stock feed's full history wins: the ETF copy would
  cut the window short.
"""

import contextlib
import io
import os
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import pit_universe

ETF = "paperswithbacktest/ETFs-Daily-Price"
STK = "paperswithbacktest/Stocks-Daily-Price"
CRP = "paperswithbacktest/Cryptocurrencies-Daily-Price"


def _bars(symbol, start, periods, price):
    dates = pd.bdate_range(start, periods=periods)
    closes = np.linspace(price, price * 1.1, periods)
    return pd.DataFrame({
        "symbol": symbol,
        "date": dates.strftime("%Y-%m-%d"),
        "open": closes,
        "high": closes * 1.01,
        "low": closes * 0.99,
        "close": closes,
        "volume": 1000,
    })


META_STOCK = _bars("META", "2020-01-01", 120, 300.0)   # 2020-01 .. 2020-06
META_ETF = _bars("META", "2020-03-02", 10, 15.0)       # a fund of two weeks
HYG_STOCK = _bars("HYG", "2019-01-01", 5, 40.0)         # a stock of one week
HYG_ETF = _bars("HYG", "2019-06-03", 200, 85.0)
SAME = _bars("SAME", "2020-01-01", 60, 50.0)
LEV_ETF = _bars("LEV", "2020-01-01", 100, 20.0)
LEV_STOCK = _bars("LEV", "2020-01-01", 102, 2.0)
CEF_STOCK = _bars("CEF", "2019-06-03", 200, 10.0)
CEF_ETF = CEF_STOCK.iloc[-60:].reset_index(drop=True)
CEF_ETF[["open", "high", "low", "close"]] *= 1.001  # adjusted copy: 0.1 % apart
AAPL = _bars("AAPL", "2020-01-01", 120, 75.0)
ABT_STOCK = _bars("ABT", "2020-01-01", 120, 90.0)
ABT_COIN = _bars("ABT", "2020-01-01", 160, 0.2)

TABLES = {
    "ETFs-Daily-Price": pd.concat([META_ETF, HYG_ETF, SAME, LEV_ETF, CEF_ETF], ignore_index=True),
    "Stocks-Daily-Price": pd.concat(
        [META_STOCK, HYG_STOCK, SAME, LEV_STOCK, CEF_STOCK, AAPL, ABT_STOCK],
        ignore_index=True
    ),
    "Cryptocurrencies-Daily-Price": ABT_COIN,
    "Universe-Daily-Price": pd.DataFrame({
        "symbol": ["META", "META", "HYG", "HYG", "SAME", "SAME", "LEV", "LEV", "CEF", "CEF",
                   "AAPL", "ABT", "ABT"],
        "repo_id": [ETF, STK, ETF, STK, ETF, STK, ETF, STK, ETF, STK, STK, STK, CRP],
        "liquidity": 1.0,
        "max_pct_change": 0.1,
    }),
}


def _membership():
    """The point-in-time universe: AAPL every session, META from March on."""
    sessions = pd.bdate_range("2020-01-01", "2020-06-30")
    aapl = pd.DataFrame({"date": sessions, "symbol": "AAPL", "rank": 1})
    meta = pd.DataFrame({"date": sessions[sessions >= "2020-03-02"], "symbol": "META", "rank": 2})
    out = pd.concat([aapl, meta], ignore_index=True)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out["dollar_volume_median"] = 1.0
    return out


TABLES["Stocks-Daily-LiquidUniverse"] = _membership()


class _FakeHub:
    """Stands in for the Hub read: returns the table, filtered like the real reader."""

    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def __call__(self, dataset_name, split, hf_token, symbols=None):
        self.calls.append((dataset_name, None if symbols is None else list(symbols)))
        df = self.tables[dataset_name].copy()
        if symbols is not None:
            df = df[df["symbol"].isin(symbols)]
        return df.reset_index(drop=True)


class CollisionRoutingTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(pit_universe._cache)
        pit_universe._cache.clear()

    def tearDown(self):
        pit_universe._cache.clear()
        pit_universe._cache.update(self.saved)

    def _pricing(self, symbols, start="2019-01-01", end="2020-12-31", **kwargs):
        hub = _FakeHub(TABLES)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_load_dataset_from_hf", hub), \
             contextlib.redirect_stdout(out):
            prices = ds.get_pricing(symbols, fields=["close"], start_date=start,
                                    end_date=end, **kwargs)
        return prices, hub, out.getvalue()

    @staticmethod
    def _close(prices, symbol):
        return prices[symbol]["close"].dropna()

    # ------------------------------------------------- point-in-time universe
    def test_universe_names_load_the_stock(self):
        prices, hub, _ = self._pricing(["sp500"])
        meta = self._close(prices, "META")
        # Membership from 2020-03-02 on, at the stock's price -- not the ETF's
        # ten sessions at 15 dollars, and not nothing.
        self.assertGreater(len(meta), 10)
        self.assertGreater(meta.min(), 250.0)
        self.assertEqual(meta.index.min(), pd.Timestamp("2020-03-02"))

    def test_universe_names_never_read_the_etf_feed(self):
        _, hub, _ = self._pricing(["sp500"])
        self.assertNotIn("ETFs-Daily-Price", [name for name, _ in hub.calls])

    def test_universe_names_uncut_load_the_stock(self):
        prices, _, _ = self._pricing(["sp500"], pit_cut=False)
        self.assertGreater(self._close(prices, "META").min(), 250.0)

    # ------------------------------------------------------- bare collisions
    def test_bare_ticker_takes_the_series_that_covers_the_window(self):
        prices, _, log = self._pricing(["META"])
        meta = self._close(prices, "META")
        self.assertEqual(len(meta), len(META_STOCK))
        self.assertGreater(meta.min(), 250.0)
        self.assertIn("'META' names two instruments", log)
        self.assertIn("META.ETF", log)

    def test_live_etf_beats_a_stock_that_held_the_ticker_briefly(self):
        prices, _, _ = self._pricing(["HYG"])
        hyg = self._close(prices, "HYG")
        self.assertEqual(len(hyg), len(HYG_ETF))
        self.assertGreater(hyg.min(), 80.0)

    def test_the_window_decides(self):
        # Inside the ETF's two weeks, the ETF has every session and the stock
        # every session too: a tie, which the priority gives to the ETF feed.
        prices, _, _ = self._pricing(["META"], start="2020-03-02", end="2020-03-13")
        self.assertLess(self._close(prices, "META").max(), 20.0)
        # Over a week in which only the stock trades, the stock.
        prices, _, _ = self._pricing(["HYG"], start="2019-01-01", end="2019-01-07")
        self.assertLess(self._close(prices, "HYG").max(), 50.0)

    def test_an_open_window_counts_every_session(self):
        # start_date=None / end_date=None mean no bound, not an empty window.
        prices, _, _ = self._pricing(["META"], start=None, end=None)
        self.assertGreater(self._close(prices, "META").min(), 250.0)

    def test_one_fund_the_etf_feed_carries_briefly_keeps_the_longer_copy(self):
        prices, _, log = self._pricing(["CEF"])
        cef = self._close(prices, "CEF")
        self.assertEqual(len(cef), len(CEF_STOCK))
        self.assertAlmostEqual(cef.iloc[-1], CEF_STOCK["close"].iloc[-1])
        self.assertNotIn("CEF", log)
        # Inside the ETF copy's sixty sessions, the ETF copy again.
        prices, _, _ = self._pricing(["CEF"], start=CEF_ETF["date"].iloc[0])
        cef = self._close(prices, "CEF")
        self.assertEqual(len(cef), len(CEF_ETF))
        self.assertAlmostEqual(cef.iloc[-1], CEF_ETF["close"].iloc[-1])

    def test_one_fund_in_both_feeds_keeps_the_etf_quietly(self):
        prices, hub, log = self._pricing(["SAME"])
        self.assertEqual(len(self._close(prices, "SAME")), len(SAME))
        self.assertNotIn("SAME", log)

    def test_one_fund_differently_adjusted_keeps_the_etf(self):
        prices, _, log = self._pricing(["LEV"])
        lev = self._close(prices, "LEV")
        self.assertEqual(len(lev), len(LEV_ETF))
        self.assertGreater(lev.min(), 15.0)
        self.assertNotIn("LEV", log)

    def test_one_series_per_ticker(self):
        prices, _, _ = self._pricing(["META", "HYG", "SAME", "AAPL"])
        self.assertEqual(
            sorted(prices.columns.get_level_values(0)), ["AAPL", "HYG", "META", "SAME"]
        )
        self.assertFalse(prices.index.duplicated().any())

    def test_suffix_still_decides(self):
        prices, _, log = self._pricing(["META.ETF"])
        self.assertLess(self._close(prices, "META").max(), 20.0)
        self.assertNotIn("two instruments", log)
        prices, _, _ = self._pricing(["HYG.STK"])
        self.assertLess(self._close(prices, "HYG").max(), 50.0)

    def test_named_next_to_the_universe_is_arbitrated_not_cut(self):
        prices, _, _ = self._pricing(["sp500", "META"])
        meta = self._close(prices, "META")
        # Named by the caller: every session of the stock, membership or not.
        self.assertEqual(len(meta), len(META_STOCK))
        self.assertGreater(meta.min(), 250.0)

    def test_other_collisions_keep_the_priority(self):
        # Stock against coin is not arbitrated: the stock reading stays.
        prices, _, _ = self._pricing(["ABT"])
        self.assertGreater(self._close(prices, "ABT").min(), 80.0)

    def test_arbitrated_symbols_are_the_etf_stock_pairs(self):
        self.assertEqual(
            ds._arbitrated_symbols(TABLES["Universe-Daily-Price"]),
            frozenset({"META", "HYG", "SAME", "LEV", "CEF"}),
        )


if __name__ == "__main__":
    unittest.main()
