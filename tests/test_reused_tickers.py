"""A bare ticker resolves, by window, to the instrument that traded under it then.

Since the price sort of 2026-11 (data-api #55) a reused ticker is published one
instrument per name: the last holder keeps the bare ticker, each earlier one is
``<TICKER>_<YYYYMMDD>``. The synthetic tables mirror the measured cases:

* ``FB`` -- Facebook as traded 2012-2022 is ``FB_20220609`` (Stocks); ``FB``
  is the buffer ETF of 2025 (ETFs).
* ``ASO`` -- AmSouth 2003-2006 is ``ASO_20061103`` (Stocks), a carbon fund of
  2009 ``ASO_20090803`` (ETFs), Academy Sports since 2020 ``ASO`` (Stocks).
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


def _bars(symbol, start, end, price):
    dates = pd.bdate_range(start, end)
    closes = np.full(len(dates), price)
    return pd.DataFrame({
        "symbol": symbol, "date": dates.strftime("%Y-%m-%d"), "open": closes,
        "high": closes, "low": closes, "close": closes, "volume": 1000,
    })


FACEBOOK = _bars("FB_20220609", "2012-05-18", "2022-06-08", 150.0)
BUFFER_ETF = _bars("FB", "2025-06-26", "2026-10-30", 25.0)
AMSOUTH = _bars("ASO_20061103", "2003-09-10", "2006-11-03", 30.0)
CARBON_FUND = _bars("ASO_20090803", "2009-06-11", "2009-07-30", 20.0)
ACADEMY = _bars("ASO", "2020-10-02", "2026-10-30", 60.0)

TABLES = {
    "Stocks-Daily-Price": pd.concat([FACEBOOK, AMSOUTH, ACADEMY], ignore_index=True),
    "ETFs-Daily-Price": pd.concat([BUFFER_ETF, CARBON_FUND], ignore_index=True),
    "Universe-Daily-Price": pd.DataFrame({
        "symbol": ["FB_20220609", "FB", "ASO_20061103", "ASO_20090803", "ASO"],
        "repo_id": [STK, ETF, STK, ETF, STK],
        "liquidity": 1.0,
        "max_pct_change": 0.1,
    }),
}


class _FakeHub:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def __call__(self, dataset_name, split, hf_token, symbols=None):
        self.calls.append((dataset_name, None if symbols is None else list(symbols)))
        df = self.tables[dataset_name].copy()
        if symbols is not None:
            df = df[df["symbol"].isin(symbols)]
        return df.reset_index(drop=True)


class ReusedTickerTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(pit_universe._cache)
        pit_universe._cache.clear()

    def tearDown(self):
        pit_universe._cache.clear()
        pit_universe._cache.update(self.saved)

    def _pricing(self, symbols, start, end):
        hub = _FakeHub(TABLES)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_load_dataset_from_hf", hub), \
             contextlib.redirect_stdout(out):
            prices = ds.get_pricing(symbols, fields=["close"], start_date=start, end_date=end)
        return prices, out.getvalue()

    def test_fb_in_2015_is_facebook(self):
        prices, log = self._pricing(["FB"], "2015-01-01", "2015-12-31")
        fb = prices["FB"]["close"].dropna()
        self.assertEqual(len(fb), len(pd.bdate_range("2015-01-01", "2015-12-31")))
        self.assertTrue((fb == 150.0).all())
        self.assertIn("'FB_20220609'", log)
        self.assertIn("loaded as 'FB'", log)

    def test_aso_in_2004_is_amsouth(self):
        prices, log = self._pricing(["ASO"], "2004-01-01", "2004-12-31")
        aso = prices["ASO"]["close"].dropna()
        self.assertTrue((aso == 30.0).all())
        self.assertIn("'ASO_20061103'", log)

    def test_aso_in_2022_is_academy_without_a_warning(self):
        prices, log = self._pricing(["ASO"], "2022-01-01", "2022-12-31")
        aso = prices["ASO"]["close"].dropna()
        self.assertTrue((aso == 60.0).all())
        self.assertNotIn("Warning", log)

    def test_a_window_over_several_instruments_takes_the_one_covering_most(self):
        prices, log = self._pricing(["ASO"], "2003-01-01", "2026-12-31")
        aso = prices["ASO"]["close"].dropna()
        # Academy: ~1 500 sessions against AmSouth's ~800; never both.
        self.assertTrue((aso == 60.0).all())
        self.assertEqual(aso.index.min(), pd.Timestamp("2020-10-02"))
        self.assertIn("'ASO_20061103'", log)
        self.assertIn("'ASO_20090803'", log)
        self.assertIn("never stitched", log)

    def test_a_dated_name_asked_for_is_loaded_as_is(self):
        prices, log = self._pricing(["ASO_20061103", "ASO"], "2003-01-01", "2026-12-31")
        self.assertTrue((prices["ASO_20061103"]["close"].dropna() == 30.0).all())
        self.assertTrue((prices["ASO"]["close"].dropna() == 60.0).all())

    def test_a_repository_suffix_resolves_within_that_repository(self):
        prices, _ = self._pricing(["ASO.STK"], "2004-01-01", "2004-12-31")
        self.assertTrue((prices["ASO"]["close"].dropna() == 30.0).all())

    def test_a_ticker_never_reused_is_untouched(self):
        prices, log = self._pricing(["FB_20220609"], "2015-01-01", "2015-12-31")
        self.assertIn("FB_20220609", prices.columns.get_level_values(0))
        self.assertNotIn("Warning", log)


if __name__ == "__main__":
    unittest.main()
