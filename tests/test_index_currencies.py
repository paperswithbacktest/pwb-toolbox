"""``to_usd`` on Indices-Daily-Price: dollars for every index that has a rate, never a silent local series.

The published table quotes each index in its own currency. The levels below are
the real closes of 2024-12-30 (DAX 19 909.14, FTSE 100 8 121.01, TAIEX 23 035.10,
WIG 79 577.32...) and the real dollar rates of that day, so a test reads like the
check it replaces: local level x XXXUSD = the dollar level.
"""

import os
import unittest
import warnings
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import index_currencies as ic

DAY = "2024-12-30"


def _bars(symbol, closes, dates):
    closes = np.asarray(closes, dtype="float64")
    return pd.DataFrame({
        "symbol": symbol,
        "date": dates,
        "open": closes * 0.99,
        "high": closes * 1.01,
        "low": closes * 0.98,
        "close": closes,
        "volume": 5,
        "adj_close": closes,
    })


def _fx(rows):
    """Forex rows as the table stores them: one spelling per pair."""
    return pd.concat([_bars(sym, [v], [d]) for sym, v, d in rows], ignore_index=True)


INDICES = pd.concat([
    _bars("DAX", [19909.14], [DAY]),
    _bars("UKX", [8121.01], [DAY]),
    _bars("TWSE", [23035.10], [DAY]),
    _bars("WIG", [79577.32], [DAY]),
    _bars("TOP40", [75381.31], [DAY]),
    _bars("XU100", [9830.56], [DAY]),
    _bars("NKY", [39894.54], [DAY]),
    _bars("BVLX", [4146.06], [DAY]),
    _bars("SPX", [5906.94], [DAY]),
    _bars("VIX", [17.4], [DAY]),
    _bars("VNINDEX", [1272.02], [DAY]),
    _bars("DSM", [10571.09], [DAY]),
], ignore_index=True)

# Stored spellings: EURUSD / GBPUSD direct, the rest USDXXX (units per dollar).
FOREX = _fx([
    ("EURUSD", 1.0400, DAY),
    ("GBPUSD", 1.2550, DAY),
    ("USDTWD", 1 / 0.03050, DAY),
    ("USDPLN", 1 / 0.24200, DAY),
    ("USDZAR", 1 / 0.05300, DAY),
    ("USDTRY", 1 / 0.02830, DAY),
    ("USDJPY", 1 / 0.00636, DAY),
])

EXPECTED_RATE = {
    "DAX": 1.0400, "UKX": 1.2550, "TWSE": 0.03050, "WIG": 0.24200,
    "TOP40": 0.05300, "XU100": 0.02830, "NKY": 0.00636, "BVLX": 1.0400,
    "SPX": 1.0, "VIX": 1.0, "DSM": 1 / 3.64,
}


class _FakeHub:
    def __init__(self, tables):
        self.tables = tables

    def __call__(self, dataset_name, split, hf_token, symbols=None):
        df = self.tables[dataset_name].copy()
        if symbols is not None:
            df = df[df["symbol"].isin(symbols)]
        return df.reset_index(drop=True)


def _load(symbols=None, to_usd=True, indices=INDICES, forex=FOREX):
    hub = _FakeHub({"Indices-Daily-Price": indices, "Forex-Daily-Price": forex})
    with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
         mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
         mock.patch.object(ds, "_load_dataset_from_hf", hub):
        return ds.load_dataset("Indices-Daily-Price", symbols=symbols, to_usd=to_usd)


def _close(df, symbol):
    return float(df.loc[df["symbol"] == symbol, "close"].iloc[0])


class TableTest(unittest.TestCase):
    def test_every_published_symbol_has_a_currency(self):
        published = {
            "ADSMI", "AEX", "AS30", "AS51", "AS52", "ASE", "ATX", "BEL20", "BELEX15",
            "BGSMDC", "BHSEEI", "BKA", "BLOM", "BSX", "BUX", "BVLX", "BVPSBVPS", "BVQA",
            "CAC", "CASE", "CCMP", "COLCAP", "CRO", "CRSMBCT", "CSEALL", "CYSMMAPA",
            "DARSDSEI", "DAX", "DFMGI", "DSEX", "DSM", "ECU", "FBMKLCI", "FSSTI", "FTN098",
            "FTSEMIB", "GGSECI", "HEX", "HEX25", "HSI", "IBEX", "IBOV", "IBVC", "ICEXI",
            "IDX:US", "IGPA", "INDEXCF", "INDU", "INDZI", "ISEQ", "JALSH", "JCI", "JMSMX",
            "JOSMGNFF", "KFX", "KNSMIDX", "KSE100", "KZKAK", "LSXC", "LUXXX", "MALTEX",
            "MBI", "MERVAL", "MEXBOL", "MONEX", "MOSENEW", "MSETOP", "MSM30", "NDX",
            "NGSEINDX", "NIFTY", "NKY", "NSEASI", "NZSE50FG", "OMX", "OSEAX", "PCOMP",
            "PFTS", "PSI20", "PX", "RIGSE", "RTY", "SASEIDX", "SASX10", "SBITOP", "SEMDEX",
            "SENSEX", "SET50", "SHCOMP", "SHSZ300", "SKSM", "SMI", "SOFIX", "SPBLPGPT",
            "SPTSX", "SPX", "SSE50", "SX5E", "TA125", "TALSE", "TEDPIX", "TOP40", "TUSISE",
            "TWSE", "UKX", "VHINDEX", "VILSE", "VIX", "VNINDEX", "VSTOXX", "VXJ", "WIG",
            "XU100",
        }
        self.assertEqual(len(published), 113)
        self.assertEqual(published - set(ic.INDEX_CURRENCY), set())

    def test_the_symbols_the_old_table_got_wrong(self):
        self.assertEqual(ic.INDEX_CURRENCY["UKX"], "GBP")
        self.assertEqual(ic.INDEX_CURRENCY["TWSE"], "TWD")
        self.assertEqual(ic.INDEX_CURRENCY["WIG"], "PLN")
        self.assertEqual(ic.INDEX_CURRENCY["TOP40"], "ZAR")
        self.assertEqual(ic.INDEX_CURRENCY["XU100"], "TRY")
        self.assertEqual(ic.INDEX_CURRENCY["BVLX"], "EUR")    # Lisbon, not Bolivia
        self.assertEqual(ic.INDEX_CURRENCY["BKA"], "KWD")     # Kuwait, not Bosnia
        self.assertEqual(ic.INDEX_CURRENCY["MSETOP"], "MNT")  # Mongolia, not Macedonia


class LoadTest(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", ic.IndexCurrencyWarning)

    def test_to_usd_false_is_the_local_level(self):
        df = _load(to_usd=False)
        self.assertAlmostEqual(_close(df, "UKX"), 8121.01)
        self.assertAlmostEqual(_close(df, "DAX"), 19909.14)
        self.assertAlmostEqual(_close(df, "VNINDEX"), 1272.02)

    def test_to_usd_true_is_local_times_the_dollar_rate(self):
        df = _load(to_usd=True)
        local = INDICES.set_index("symbol")["close"]
        for symbol, rate in EXPECTED_RATE.items():
            with self.subTest(symbol=symbol):
                self.assertAlmostEqual(_close(df, symbol), local[symbol] * rate, places=6)

    def test_ukx_is_no_longer_left_in_pounds(self):
        df = _load(symbols=["UKX"], to_usd=True)
        self.assertAlmostEqual(_close(df, "UKX"), 8121.01 * 1.2550, places=6)

    def test_open_is_converted_at_the_pair_open(self):
        df = _load(symbols=["UKX"], to_usd=True)
        # index open 8121.01 * 0.99, GBPUSD open 1.2550 * 0.99 (same-day market quote)
        self.assertAlmostEqual(float(df["open"].iloc[0]), 8121.01 * 0.99 * 1.2550 * 0.99, places=6)

    def test_pegged_currency_uses_one_rate_for_all_columns(self):
        df = _load(symbols=["DSM"], to_usd=True)
        self.assertAlmostEqual(float(df["open"].iloc[0]), 10571.09 * 0.99 / 3.64, places=6)

    def test_high_stays_above_low(self):
        df = _load(symbols=["NKY", "UKX"], to_usd=True)
        self.assertTrue((df["high"] >= df["low"]).all())
        self.assertTrue((df["volume"] == 5).all())

    def test_unconvertible_symbol_asked_by_name_raises(self):
        with self.assertRaisesRegex(ValueError, "VNINDEX.*to_usd=False"):
            _load(symbols=["VNINDEX"], to_usd=True)

    def test_unconvertible_rows_are_dropped_with_a_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            df = _load(to_usd=True)
        self.assertNotIn("VNINDEX", set(df["symbol"]))
        messages = [str(w.message) for w in caught if issubclass(w.category, ic.IndexCurrencyWarning)]
        self.assertTrue(any("VNINDEX [VND]" in m for m in messages))


class RateRulesTest(unittest.TestCase):
    def test_stale_quote_within_tolerance_is_used(self):
        fx = ic._fx_table(_fx([("GBPUSD", 1.25, "2024-12-24")]))
        days = pd.DatetimeIndex(["2024-12-27", "2025-01-10"])
        rate = ic.currency_rate(fx, "GBP", days)
        self.assertAlmostEqual(rate[0], 1.25)
        self.assertTrue(np.isnan(rate[1]))

    def test_hard_peg_beats_a_spiky_pair(self):
        fx = ic._fx_table(_fx([("AEDUSD", 1.99, "2016-11-08")]))
        rate = ic.currency_rate(fx, "AED", pd.DatetimeIndex(["2016-11-08"]))
        self.assertAlmostEqual(rate[0], 1 / 3.6725)

    def test_late_euro_adopter_is_continuous_across_the_changeover(self):
        # Kuna before 2023, at 7.5345 per euro; the dollar series must not jump.
        fx = ic._fx_table(_fx([
            ("HRKUSD", 1.07 / 7.5345, "2022-12-30"),
            ("EURUSD", 1.07, "2023-01-02"),
        ]))
        rate = ic.index_rate(fx, "CRO", pd.DatetimeIndex(["2022-12-30", "2023-01-02"]))
        self.assertAlmostEqual(rate[0], rate[1])

    def test_legacy_currency_without_a_rate_is_not_converted_with_the_euro(self):
        fx = ic._fx_table(_fx([("EURUSD", 1.10, "2005-06-01")]))
        rate = ic.index_rate(fx, "SKSM", pd.DatetimeIndex(["2005-06-01"]))
        self.assertTrue(np.isnan(rate[0]))

    def test_euro_pegged_legacy_currency_uses_eurusd(self):
        fx = ic._fx_table(_fx([("EURUSD", 1.30, "2008-06-02")]))
        rate = ic.index_rate(fx, "TALSE", pd.DatetimeIndex(["2008-06-02"]))
        self.assertAlmostEqual(rate[0], 1.30)


if __name__ == "__main__":
    unittest.main()
