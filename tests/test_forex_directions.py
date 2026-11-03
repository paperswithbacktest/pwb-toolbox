"""A forex pair loads under either spelling, from the one series the table keeps.

The synthetic tables mirror the two states of ``Forex-Daily-Price``:

* ``REPUBLISHED`` -- one spelling per pair, as after data-api #52: ``USDJPY``
  (yen per dollar) and ``XAUUSD`` (dollars per ounce), plus ``EURUSD``.
* ``PUBLISHED`` -- the table as it stands, with a later-starting stub of the
  other spelling beside each long series (``JPYUSD``, ``USDXAU``).
"""

import os
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as ds

DATES = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]


def _bars(symbol, closes, dates=DATES, volume=7):
    closes = np.asarray(closes, dtype="float64")
    return pd.DataFrame({
        "symbol": symbol,
        "date": dates[: len(closes)],
        "open": closes * 0.99,
        "high": closes * 1.02,
        "low": closes * 0.97,
        "close": closes,
        "volume": volume,
    })


USDJPY = _bars("USDJPY", [108.0, 109.0, 110.0, 111.0])
XAUUSD = _bars("XAUUSD", [1500.0, 1510.0, 1520.0, 1530.0])
EURUSD = _bars("EURUSD", [1.10, 1.11, 1.12, 1.13])
# Stubs: start later than the long series, and deliberately off by a few bp,
# so a test can tell which series answered.
JPYUSD_STUB = _bars("JPYUSD", [1 / 109.5, 1 / 110.5, 1 / 111.5], dates=DATES[1:])
USDXAU_STUB = _bars("USDXAU", [1 / 1511.0, 1 / 1521.0, 1 / 1531.0], dates=DATES[1:])

REPUBLISHED = pd.concat([USDJPY, XAUUSD, EURUSD], ignore_index=True)
PUBLISHED = pd.concat([REPUBLISHED, JPYUSD_STUB, USDXAU_STUB], ignore_index=True)

UNIVERSE_REPUBLISHED = pd.DataFrame({
    "symbol": ["USDJPY", "XAUUSD", "EURUSD", "AAPL"],
    "repo_id": ["paperswithbacktest/Forex-Daily-Price"] * 3 + ["paperswithbacktest/Stocks-Daily-Price"],
    "liquidity": [1.0, 1.0, 1.0, 1.0],
    "max_pct_change": [0.1, 0.1, 0.1, 0.1],
})


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


class ForexDirectionTest(unittest.TestCase):
    def _load(self, table, **kwargs):
        hub = _FakeHub({"Forex-Daily-Price": table})
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_load_dataset_from_hf", hub):
            df = ds.load_dataset("Forex-Daily-Price", **kwargs)
        return df, hub

    @staticmethod
    def _series(df, symbol):
        out = df[df["symbol"] == symbol].copy()
        out["date"] = out["date"].astype(str)
        return out.set_index("date").sort_index()

    # ----------------------------------------------------------- the helpers
    def test_inverse_spelling(self):
        self.assertEqual(ds.forex_inverse("USDJPY"), "JPYUSD")
        self.assertEqual(ds.forex_inverse("XAUUSD"), "USDXAU")
        self.assertEqual(ds.forex_inverse("SPX"), "SPX")

    def test_inverted_bars_swap_high_and_low(self):
        bar = _bars("USDJPY", [100.0])
        bar["adj_close"] = 50.0
        inv = ds._invert_quotes(bar).iloc[0]
        self.assertAlmostEqual(inv["open"], 1 / 99.0)
        self.assertAlmostEqual(inv["high"], 1 / 97.0)   # 1 / low
        self.assertAlmostEqual(inv["low"], 1 / 102.0)   # 1 / high
        self.assertAlmostEqual(inv["close"], 1 / 100.0)
        self.assertAlmostEqual(inv["adj_close"], 1 / 50.0)
        self.assertEqual(inv["volume"], 7)
        self.assertGreaterEqual(inv["high"], inv["low"])

    def test_shadow_rule_matches_the_publication(self):
        self.assertEqual(
            ds.forex_shadow_directions(PUBLISHED),
            {"JPYUSD": "USDJPY", "USDXAU": "XAUUSD"},
        )
        self.assertEqual(ds.forex_shadow_directions(REPUBLISHED), {})

    # ---------------------------------------- the republished table, raw spelling
    def test_dropped_spelling_is_served_inverted_without_to_usd(self):
        df, hub = self._load(REPUBLISHED, symbols=["JPYUSD"], to_usd=False)
        self.assertEqual(set(df["symbol"]), {"JPYUSD"})
        self.assertEqual(set(hub.calls[0][1]), {"JPYUSD", "USDJPY"})
        jpy = self._series(df, "JPYUSD")
        raw = self._series(USDJPY, "USDJPY")
        np.testing.assert_allclose(jpy["close"], 1 / raw["close"])
        np.testing.assert_allclose(jpy["open"], 1 / raw["open"])
        np.testing.assert_allclose(jpy["high"], 1 / raw["low"])
        np.testing.assert_allclose(jpy["low"], 1 / raw["high"])
        np.testing.assert_array_equal(jpy["volume"], raw["volume"])
        self.assertTrue((jpy["high"] >= jpy["low"]).all())

    def test_kept_spelling_is_raw_without_to_usd(self):
        df, _ = self._load(REPUBLISHED, symbols=["USDJPY", "XAUUSD"], to_usd=False)
        pd.testing.assert_frame_equal(
            self._series(df, "USDJPY"), self._series(USDJPY, "USDJPY"), check_dtype=False
        )
        self.assertEqual(set(df["symbol"]), {"USDJPY", "XAUUSD"})

    def test_metals_from_the_dollar_side(self):
        df, _ = self._load(REPUBLISHED, symbols=["USDXAU", "USDXAG"], to_usd=False)
        self.assertEqual(set(df["symbol"]), {"USDXAU"})  # no silver in the table
        np.testing.assert_allclose(
            self._series(df, "USDXAU")["close"], 1 / XAUUSD["close"].values
        )

    def test_both_spellings_at_once_without_to_usd(self):
        df, _ = self._load(REPUBLISHED, symbols=["USDJPY", "JPYUSD"], to_usd=False)
        usd = self._series(df, "USDJPY")
        jpy = self._series(df, "JPYUSD")
        self.assertEqual(len(usd), 4)
        self.assertEqual(len(jpy), 4)
        np.testing.assert_allclose(usd["close"] * jpy["close"], 1.0)
        np.testing.assert_allclose(usd["high"] * jpy["low"], 1.0)

    # ------------------------------------------- the republished table, to_usd
    def test_to_usd_inverts_once_whatever_the_spelling(self):
        for asked in (["JPYUSD"], ["USDJPY"], ["USDJPY", "JPYUSD"]):
            with self.subTest(asked=asked):
                df, _ = self._load(REPUBLISHED, symbols=asked)
                self.assertEqual(set(df["symbol"]), {"JPYUSD"})
                jpy = self._series(df, "JPYUSD")
                self.assertEqual(len(jpy), 4)  # one series, never twice
                np.testing.assert_allclose(jpy["close"], 1 / USDJPY["close"].values)
                np.testing.assert_allclose(jpy["high"], 1 / USDJPY["low"].values)
                self.assertTrue((jpy["high"] >= jpy["low"]).all())

    def test_to_usd_leaves_dollar_quoted_pairs_alone(self):
        df, _ = self._load(REPUBLISHED, symbols=["XAUUSD", "USDXAU", "EURUSD"])
        self.assertEqual(set(df["symbol"]), {"XAUUSD", "EURUSD"})
        pd.testing.assert_series_equal(
            self._series(df, "XAUUSD")["close"],
            self._series(XAUUSD, "XAUUSD")["close"],
            check_dtype=False,
        )

    # ---------------------------------- the table as published today (two spellings)
    def test_published_table_loads_as_the_republished_one(self):
        cases = [
            (["JPYUSD"], False), (["USDJPY"], False), (["USDJPY", "JPYUSD"], False),
            (["USDXAU"], False), (["XAUUSD", "USDXAU"], False),
            (["JPYUSD"], True), (["USDJPY", "JPYUSD"], True), (["USDXAU"], True),
            (None, True), (None, False),
        ]
        for asked, to_usd in cases:
            with self.subTest(asked=asked, to_usd=to_usd):
                before, _ = self._load(PUBLISHED, symbols=asked, to_usd=to_usd)
                after, _ = self._load(REPUBLISHED, symbols=asked, to_usd=to_usd)
                key = ["symbol", "date"]
                pd.testing.assert_frame_equal(
                    before.sort_values(key).reset_index(drop=True),
                    after.sort_values(key).reset_index(drop=True),
                    check_dtype=False,
                )

    def test_published_full_load_no_longer_doubles_dates(self):
        df, _ = self._load(PUBLISHED)
        self.assertFalse(df.duplicated(["symbol", "date"]).any())
        self.assertEqual(set(df["symbol"]), {"JPYUSD", "XAUUSD", "EURUSD"})

    # ------------------------------------------------------- routing by the index
    def test_index_routes_the_other_spelling_to_forex(self):
        out = ds._with_forex_inverse_names(UNIVERSE_REPUBLISHED)
        routes = ds._bare_symbol_routes(out)
        for name in ("JPYUSD", "USDXAU", "USDEUR", "USDJPY"):
            self.assertEqual(routes[name], "paperswithbacktest/Forex-Daily-Price")
        self.assertEqual(routes["AAPL"], "paperswithbacktest/Stocks-Daily-Price")
        self.assertEqual(len(out), len(UNIVERSE_REPUBLISHED) + 3)

    def test_index_never_overrides_a_known_name(self):
        universe = pd.concat([
            UNIVERSE_REPUBLISHED,
            pd.DataFrame({"symbol": ["JPYUSD"], "repo_id": ["paperswithbacktest/Stocks-Daily-Price"],
                          "liquidity": [1.0], "max_pct_change": [0.1]}),
        ], ignore_index=True)
        routes = ds._bare_symbol_routes(ds._with_forex_inverse_names(universe))
        self.assertEqual(routes["JPYUSD"], "paperswithbacktest/Stocks-Daily-Price")

    def test_get_pricing_serves_a_dropped_spelling(self):
        hub = _FakeHub({
            "Forex-Daily-Price": REPUBLISHED,
            "Universe-Daily-Price": UNIVERSE_REPUBLISHED,
        })
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_load_dataset_from_hf", hub):
            prices = ds.get_pricing(["JPYUSD", "EURUSD"], fields=["close", "high", "low"],
                                    start_date="2020-01-01", end_date="2020-12-31")
        self.assertEqual(set(prices.columns.get_level_values(0)), {"JPYUSD", "EURUSD"})
        np.testing.assert_allclose(prices["JPYUSD"]["close"].values, 1 / USDJPY["close"].values)
        self.assertTrue((prices["JPYUSD"]["high"] >= prices["JPYUSD"]["low"]).all())


if __name__ == "__main__":
    unittest.main()
