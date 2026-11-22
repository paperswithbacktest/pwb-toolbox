"""Kenneth French Data Library loader, on synthetic fixtures (no network).

The fixture CSVs in ``tests/data/french`` copy the layout of the library's
files (title lines, untitled factor tables, annual tables, weighted return
tables, characteristic tables, trailing commas, ``-99.99``/``-999``) with
made-up numbers: none of the library's data is in this repository. Each is
zipped at test time and served by a fake ``_http_get``.

``PWB_NETWORK_TESTS=1`` also runs one test against the real site.
"""

import io
import os
import shutil
import tempfile
import unittest
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import requests

from pwb_toolbox.datasets import french

FIXTURES = Path(__file__).resolve().parent / "data" / "french"


def _zip(csv_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(csv_name, (FIXTURES / csv_name).read_bytes())
    return buf.getvalue()


def _server():
    """``{url: payload}`` for the fixture site."""
    site = {french.BASE_URL + french.LIBRARY_PAGE: (FIXTURES / "data_library.html").read_bytes()}
    for csv_name, zip_name in [
        ("F-F_Research_Data_Factors.csv", "F-F_Research_Data_Factors_CSV.zip"),
        ("F-F_Research_Data_Factors_daily.csv", "F-F_Research_Data_Factors_daily_CSV.zip"),
        ("F-F_Momentum_Factor.csv", "F-F_Momentum_Factor_CSV.zip"),
        ("3_Industry_Portfolios.csv", "3_Industry_Portfolios_CSV.zip"),
        ("4_Portfolios_2x2_Daily.csv", "4_Portfolios_2x2_Daily_CSV.zip"),
        ("2_Portfolios_BM.csv", "2_Portfolios_BM_CSV.zip"),
        ("Portfolios_Formed_on_X.csv", "Portfolios_Formed_on_X_CSV.zip"),
    ]:
        site[french.BASE_URL + "ftp/" + zip_name] = _zip(csv_name)
    return site


class FrenchTestCase(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp(prefix="pwb-french-")
        self.addCleanup(shutil.rmtree, self.cache, True)
        self.site = _server()
        self.requests = []

        def fake_get(url):
            self.requests.append(url)
            if url not in self.site:
                raise requests.HTTPError(f"404 {url}")
            return self.site[url]

        patcher = mock.patch.object(french, "_http_get", side_effect=fake_get)
        patcher.start()
        self.addCleanup(patcher.stop)

    def load(self, *args, **kwargs):
        kwargs.setdefault("cache_dir", self.cache)
        return french.load_french(*args, **kwargs)

    def blocks(self, *args, **kwargs):
        kwargs.setdefault("cache_dir", self.cache)
        return french.load_french_blocks(*args, **kwargs)


class BlockFormats(FrenchTestCase):
    """One test per table layout the library publishes."""

    def test_untitled_monthly_factor_table(self):
        ff3 = self.load("ff3")
        self.assertEqual(list(ff3.columns), ["Mkt-RF", "SMB", "HML", "RF"])
        self.assertEqual(list(ff3.index), [pd.Timestamp("1926-07-31"), pd.Timestamp("1926-08-31")])
        self.assertAlmostEqual(ff3.loc["1926-07-31", "Mkt-RF"], 0.02)
        self.assertAlmostEqual(ff3.loc["1926-08-31", "RF"], 0.0025)
        self.assertTrue(np.isnan(ff3.loc["1926-08-31", "HML"]))  # -99.99
        self.assertEqual(ff3.index.name, "date")
        self.assertEqual(ff3.attrs["kind"], "returns")
        self.assertEqual(ff3.attrs["crsp_vintage"], "202609")

    def test_annual_factor_table_on_one_line(self):
        annual = self.load("ff3", frequency="annual")
        self.assertEqual(list(annual.index), [pd.Timestamp("1927-12-31")])
        self.assertAlmostEqual(annual.iloc[0]["Mkt-RF"], 0.10)

    def test_annual_title_on_two_lines_and_minus_999(self):
        blocks = self.blocks("mom")
        self.assertEqual(list(blocks), ["monthly", "annual"])
        self.assertEqual(blocks["annual"].attrs["title"], "Annual Factors: January-December")
        self.assertTrue(np.isnan(blocks["monthly"].loc["1927-02-28", "Mom"]))
        self.assertAlmostEqual(blocks["annual"].iloc[0, 0], 0.12)

    def test_daily_factor_table(self):
        daily = self.load("ff3", frequency="daily")
        self.assertEqual(len(daily), 3)
        self.assertEqual(daily.index[0], pd.Timestamp("1926-07-01"))
        self.assertAlmostEqual(daily.loc["1926-07-06", "HML"], 0.009)
        self.assertEqual(daily.attrs["frequency"], "daily")

    def test_weighted_portfolio_tables_and_characteristics(self):
        blocks = self.blocks("3_Industry_Portfolios")
        self.assertEqual(list(blocks), [
            "value_monthly", "equal_monthly", "value_annual", "equal_annual",
            "number_of_firms_in_portfolios", "average_firm_size",
        ])
        vw = self.load("3_Industry_Portfolios")
        ew = self.load("3_Industry_Portfolios", weighting="equal")
        self.assertEqual(list(vw.columns), ["Agric", "Food", "Soda"])  # trailing comma dropped
        self.assertAlmostEqual(vw.loc["1926-08-31", "Soda"], 0.05)
        self.assertTrue(np.isnan(vw.loc["1926-07-31", "Soda"]))
        self.assertAlmostEqual(ew.loc["1926-07-31", "Agric"], 0.06)
        self.assertAlmostEqual(self.load("3_Industry_Portfolios", frequency="annual",
                                         weighting="equal").iloc[0]["Soda"], 0.41)
        firms = blocks["number_of_firms_in_portfolios"]
        self.assertEqual(firms.attrs["kind"], "characteristic")
        self.assertEqual(firms.loc["1926-08-31", "Food"], 41)  # not divided by 100
        size = self.load("3_Industry_Portfolios", block="average_firm_size")
        self.assertAlmostEqual(size.loc["1926-07-31", "Soda"], 300.25)
        self.assertTrue(np.isnan(size.loc["1926-07-31", "Food"]))

    def test_daily_portfolio_file_with_capital_daily(self):
        # The site writes "_daily" for factors and "_Daily" for portfolios.
        vw = self.load("4_Portfolios_2x2", frequency="daily")
        self.assertEqual(list(vw.columns), ["SMALL LoBM", "SMALL HiBM", "BIG LoBM", "BIG HiBM"])
        self.assertAlmostEqual(vw.loc["2024-01-03", "BIG HiBM"], -0.004)
        self.assertEqual(vw.attrs["file"], "4_Portfolios_2x2_Daily_CSV.zip")
        ew = self.load("4_Portfolios_2x2", frequency="daily", weighting="equal")
        self.assertAlmostEqual(ew.loc["2024-01-02", "SMALL LoBM"], 0.011)

    def test_multi_line_characteristic_titles_keep_distinct_keys(self):
        blocks = self.blocks("2_Portfolios_BM")
        keys = list(blocks)
        self.assertEqual(keys[0], "value_monthly")
        self.assertEqual(len(keys), 3)
        self.assertNotEqual(keys[1], keys[2])
        self.assertTrue(keys[1].startswith("value_weight_average_of_be_me"))
        # "Value Weight Average of BE/ME" is not a return table: left as published.
        self.assertEqual(blocks[keys[1]].attrs["kind"], "characteristic")
        self.assertAlmostEqual(blocks[keys[1]].iloc[0, 1], 1.5690)

    def test_weight_titles_and_rows_after_a_blank_line(self):
        # "Value Weight Returns" (no "-ed"), and annual rows one blank line
        # below their header, as in Portfolios_Formed_on_ME / _E-P / _VAR.
        blocks = self.blocks("Portfolios_Formed_on_X")
        self.assertEqual(list(blocks), [
            "value_monthly", "equal_monthly", "value_annual", "equal_annual",
            "value_weight_average_of_e_me",
        ])
        self.assertAlmostEqual(self.load("Portfolios_Formed_on_X", weighting="equal").iloc[0, 1], 0.04)
        annual = self.load("Portfolios_Formed_on_X", frequency="annual")
        self.assertEqual(annual.index[0], pd.Timestamp("1964-12-31"))
        self.assertAlmostEqual(annual.iloc[0, 0], 0.157)
        self.assertEqual(blocks["value_weight_average_of_e_me"].attrs["kind"], "characteristic")


class Resolution(FrenchTestCase):
    def test_listing_parses_csv_zips_only(self):
        names = french.french_datasets(cache_dir=self.cache)
        self.assertIn("F-F_Research_Data_Factors", names)
        self.assertIn("4_Portfolios_2x2_Daily", names)
        self.assertNotIn("F-F_Research_Data_Factors_TXT", names)

    def test_aliases_cover_the_required_files(self):
        for alias, stem in {
            "ff3": "F-F_Research_Data_Factors", "ff5": "F-F_Research_Data_5_Factors_2x3",
            "mom": "F-F_Momentum_Factor", "st_rev": "F-F_ST_Reversal_Factor",
            "lt_rev": "F-F_LT_Reversal_Factor", "ind48": "48_Industry_Portfolios",
            "ind49": "49_Industry_Portfolios", "25_size_bm": "25_Portfolios_5x5",
            "100_size_bm": "100_Portfolios_10x10",
        }.items():
            self.assertEqual(french.FRENCH_ALIASES[alias], stem)
        for n in (10, 12, 17, 30, 38):
            self.assertIn(f"ind{n}", french.FRENCH_ALIASES)

    def test_unknown_name_suggests_close_ones(self):
        with self.assertRaises(french.FrenchDataError) as ctx:
            self.load("3_Industry_Portfolio")
        self.assertIn("3_Industry_Portfolios", str(ctx.exception))

    def test_breakpoint_files_are_refused(self):
        with self.assertRaises(french.FrenchDataError):
            self.load("ME_Breakpoints")
        self.assertEqual(self.requests, [])

    def test_average_of_prior_returns_is_a_characteristic(self):
        self.assertEqual(french._kind_and_weighting("Value-Weighted Average of Prior Returns"),
                         ("characteristic", "value"))
        self.assertEqual(french._kind_and_weighting("Average Value Weighted Returns -- Monthly"),
                         ("returns", "value"))

    def test_missing_frequency_is_refused(self):
        with self.assertRaises(french.FrenchDataError):
            self.load("mom", frequency="daily")  # not in the fixture listing
        with self.assertRaises(ValueError):
            self.load("ff3", frequency="quarterly")

    def test_licence_and_provenance_in_attrs(self):
        ff3 = self.load("ff3")
        self.assertEqual(ff3.attrs["source"], french.SOURCE)
        self.assertIn("not redistributed", ff3.attrs["licence"])
        self.assertTrue(ff3.attrs["url"].endswith("ftp/F-F_Research_Data_Factors_CSV.zip"))
        datetime.fromisoformat(ff3.attrs["downloaded_at"])


class Cache(FrenchTestCase):
    def test_second_load_makes_no_request(self):
        first = self.load("ff3")
        n = len(self.requests)
        second = self.load("ff3")
        self.assertEqual(len(self.requests), n)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first.attrs["downloaded_at"], second.attrs["downloaded_at"])

    def test_copies_are_timestamped(self):
        self.load("ff3")
        copies = french._cached_copies(self.cache, "F-F_Research_Data_Factors_CSV.zip")
        self.assertEqual(len(copies), 1)
        self.assertRegex(os.path.basename(copies[0][1]), r"\.\d{8}T\d{6}Z$")

    def test_refresh_downloads_again_and_keeps_one_copy(self):
        self.load("ff3")
        stale = datetime.now(timezone.utc) - timedelta(days=30)
        (_, path), = french._cached_copies(self.cache, "F-F_Research_Data_Factors_CSV.zip")
        os.rename(path, path.rsplit(".", 1)[0] + "." + french._stamp(stale))
        self.requests.clear()
        self.load("ff3", refresh=True)
        self.assertIn(french.BASE_URL + "ftp/F-F_Research_Data_Factors_CSV.zip", self.requests)
        copies = french._cached_copies(self.cache, "F-F_Research_Data_Factors_CSV.zip")
        self.assertEqual(len(copies), 1)
        self.assertGreater(copies[0][0], stale)

    def test_stale_copy_is_downloaded_again(self):
        self.load("ff3")
        (_, path), = french._cached_copies(self.cache, "F-F_Research_Data_Factors_CSV.zip")
        old = datetime.now(timezone.utc) - timedelta(days=10)
        os.rename(path, path.rsplit(".", 1)[0] + "." + french._stamp(old))
        self.requests.clear()
        self.load("ff3", max_age_days=7)
        self.assertTrue(any(u.endswith("F-F_Research_Data_Factors_CSV.zip") for u in self.requests))

    def test_offline_falls_back_to_stale_copy_with_warning(self):
        self.load("ff3")
        for path in Path(self.cache).iterdir():
            base, _ = str(path).rsplit(".", 1)
            os.rename(path, base + "." + french._stamp(datetime(2020, 1, 1, tzinfo=timezone.utc)))
        self.site.clear()  # the site is gone
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ff3 = self.load("ff3")
        self.assertAlmostEqual(ff3.iloc[0, 0], 0.02)
        self.assertTrue(ff3.attrs["downloaded_at"].startswith("2020-01-01"))
        self.assertTrue(any("could not download" in str(w.message) for w in caught))

    def test_offline_without_cache_raises(self):
        self.site.clear()
        with self.assertRaises(requests.RequestException):
            self.load("ff3")

    def test_corrupt_download_is_not_cached(self):
        self.site[french.BASE_URL + "ftp/F-F_Research_Data_Factors_CSV.zip"] = b"<html>error</html>"
        with self.assertRaises(ValueError):
            self.load("ff3")
        self.assertEqual(french._cached_copies(self.cache, "F-F_Research_Data_Factors_CSV.zip"), [])

    def test_default_cache_dir(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(french.french_cache_dir().endswith(os.path.join(".cache", "pwb", "french")))
        with mock.patch.dict(os.environ, {"PWB_CACHE_DIR": "/tmp/x"}, clear=True):
            self.assertEqual(french.french_cache_dir(), os.path.join("/tmp/x", "french"))
        with mock.patch.dict(os.environ, {"PWB_FRENCH_CACHE_DIR": "/tmp/y", "PWB_CACHE_DIR": "/tmp/x"}):
            self.assertEqual(french.french_cache_dir(), "/tmp/y")


@unittest.skipUnless(os.getenv("PWB_NETWORK_TESTS") == "1",
                     "network test: set PWB_NETWORK_TESTS=1 to run it")
class Network(unittest.TestCase):
    """Against the real site: the listing, FF5 monthly and 48 industries daily."""

    network = True

    def test_real_site(self):
        cache = tempfile.mkdtemp(prefix="pwb-french-net-")
        self.addCleanup(shutil.rmtree, cache, True)
        names = french.french_datasets(cache_dir=cache)
        self.assertIn("F-F_Research_Data_5_Factors_2x3", names)
        ff5 = french.load_french("ff5", cache_dir=cache)
        self.assertEqual(list(ff5.columns), ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"])
        self.assertEqual(ff5.index[0], pd.Timestamp("1963-07-31"))
        self.assertLess(ff5.abs().max().max(), 1.0)  # decimals, not percents
        ind = french.load_french("ind48", frequency="daily", cache_dir=cache)
        self.assertEqual(ind.shape[1], 48)
        for alias in ("ff3", "mom", "st_rev", "lt_rev", "ind10", "ind12", "ind17",
                      "ind30", "ind38", "ind49", "25_size_bm", "100_size_bm"):
            for freq in ("monthly", "daily"):
                frame = french.load_french(alias, frequency=freq, cache_dir=cache)
                self.assertGreater(len(frame), 100, (alias, freq))


if __name__ == "__main__":
    unittest.main()
