"""Bounded reads of the sharded datasets: ``load_dataset(start=, end=, columns=)``.

Fake monthly shards are written to a temporary directory and served through
mocks of the Hub snapshot, ``hf_hub_download`` and the subscriber API: nothing
here touches the network.
"""

import os
import shutil
import tempfile
import unittest
import warnings
from unittest import mock

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds

SYMBOLS = ["AAA", "BBB", "CCC"]
MONTHS = ["2024-01", "2024-02", "2024-03"]


def _minute_month(month: str) -> pd.DataFrame:
    """Three symbols, bars at 09:30, 12:00 and 15:59 of every calendar day, the
    timestamps stored as strings like the published minute tables."""
    days = pd.date_range(f"{month}-01", periods=pd.Period(month).days_in_month, freq="D")
    rows = []
    for day in days:
        for clock in ("09:30:00", "12:00:00", "15:59:00"):
            for i, symbol in enumerate(SYMBOLS):
                stamp = f"{day:%Y-%m-%d} {clock}"
                price = 100.0 * (i + 1) + day.day
                rows.append((symbol, stamp, price, price + 0.5, 10 * (i + 1)))
    df = pd.DataFrame(rows, columns=["symbol", "datetime", "adj_open", "adj_close", "volume"])
    return df.sort_values(["datetime", "symbol"], kind="stable").reset_index(drop=True)


def _write(df: pd.DataFrame, path: str, row_group_size: int = 90) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, row_group_size=row_group_size)


class _Repo:
    """A fake dataset repository on disk and the mocks that serve it."""

    def __init__(self, root: str, frames: dict):
        self.root = root
        self.files = []
        for name, df in frames.items():
            _write(df, os.path.join(root, name))
            self.files.append(name)
        self.downloaded = []

    def download(self, **kw):
        self.downloaded.append(kw["filename"])
        return os.path.join(self.root, kw["filename"])

    def patches(self):
        return [
            mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}),
            mock.patch.object(ds, "_get_pwb_api_key", return_value=None),
            mock.patch.object(ds, "_hub_snapshot", return_value=("sha", ["README.md", *sorted(self.files)])),
            mock.patch.object(ds, "hf_hub_download", side_effect=self.download),
        ]


class BoundedLoaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.frames = {f"data/train-{m}.parquet": _minute_month(m) for m in MONTHS}
        self.repo = _Repo(self.tmp, self.frames)
        self.full = pd.concat(self.frames.values(), ignore_index=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _load(self, name="Test-1Min-Price", **kwargs):
        patches = self.repo.patches()
        for p in patches:
            p.start()
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                df = ds.load_dataset(name, **kwargs)
        finally:
            for p in reversed(patches):
                p.stop()
        return df, caught

    # -- shard selection --------------------------------------------------
    def test_only_the_months_of_the_window_are_downloaded(self):
        df, _ = self._load(symbols=["BBB"], start="2024-02-10", end="2024-02-20",
                           columns=["adj_close"])
        self.assertEqual(self.repo.downloaded, ["data/train-2024-02.parquet"])
        self.assertEqual(list(df.columns), ["symbol", "datetime", "adj_close"])
        self.assertEqual(set(df["symbol"]), {"BBB"})
        self.assertEqual(df["datetime"].min(), pd.Timestamp("2024-02-10 09:30"))
        self.assertEqual(df["datetime"].max(), pd.Timestamp("2024-02-20 15:59"))
        self.assertEqual(len(df), 11 * 3)

    def test_a_bare_end_date_keeps_its_whole_day_and_the_next_shard_is_only_slack(self):
        df, _ = self._load(symbols=["AAA"], start="2024-01-31", end="2024-01-31")
        # One day of slack around a month boundary: the next shard is opened
        # in case its timestamps were shifted by a time-zone conversion.
        self.assertEqual(self.repo.downloaded, ["data/train-2024-01.parquet", "data/train-2024-02.parquet"])
        self.assertEqual(list(df["datetime"].dt.strftime("%H:%M")), ["09:30", "12:00", "15:59"])
        self.assertTrue((df["datetime"].dt.date == pd.Timestamp("2024-01-31").date()).all())

    def test_bounds_with_a_time_of_day_are_inclusive(self):
        df, _ = self._load(symbols=["AAA"], start="2024-03-05 12:00", end="2024-03-06 12:00")
        self.assertEqual(
            list(df["datetime"].dt.strftime("%m-%d %H:%M")),
            ["03-05 12:00", "03-05 15:59", "03-06 09:30", "03-06 12:00"],
        )

    def test_open_ended_windows(self):
        df, _ = self._load(symbols=["CCC"], start="2024-03-30")
        self.assertEqual(self.repo.downloaded, ["data/train-2024-03.parquet"])
        self.assertEqual(df["datetime"].dt.date.nunique(), 2)
        self.repo.downloaded.clear()
        df, _ = self._load(symbols=["CCC"], end="2024-01-02")
        self.assertEqual(self.repo.downloaded, ["data/train-2024-01.parquet"])
        self.assertEqual(df["datetime"].dt.date.nunique(), 2)

    def test_a_window_outside_the_dataset_warns_and_downloads_nothing(self):
        df, caught = self._load(symbols=["AAA"], start="2019-01-01", end="2019-12-31",
                                columns=["adj_close"])
        self.assertEqual(self.repo.downloaded, [])
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ["symbol", "adj_close"])
        self.assertTrue(any("2024-01-01..2024-03-31" in str(w.message) for w in caught))

    # -- read: rows and columns filtered before pandas ---------------------
    def test_the_parquet_read_receives_the_filters_and_the_projection(self):
        calls = []
        real = pd.read_parquet

        def spy(source, **kw):
            out = real(source, **kw)
            calls.append((kw, len(out)))
            return out

        with mock.patch.object(ds.pd, "read_parquet", side_effect=spy):
            self._load(symbols=["AAA"], start="2024-02-01", end="2024-02-01", columns=["volume"])
        (kw, rows), = [c for c in calls if c[1]]  # the Feb shard; Jan/Mar give nothing
        self.assertEqual(kw["columns"], ["symbol", "datetime", "volume"])
        self.assertIn(("symbol", "in", ["AAA"]), kw["filters"])
        self.assertIn(("datetime", ">=", "2024-02-01"), kw["filters"])
        self.assertIn(("datetime", "<", "2024-02-02"), kw["filters"])
        self.assertEqual(rows, 3)  # what pandas got: the three bars, not the 1 044-row shard

    def test_unknown_columns_are_an_error(self):
        with self.assertRaisesRegex(ValueError, "unknown columns"):
            self._load(symbols=["AAA"], start="2024-01-01", end="2024-01-02", columns=["close"])

    def test_bad_windows_are_refused(self):
        with self.assertRaisesRegex(ValueError, "after end"):
            self._load(start="2024-02-02", end="2024-02-01")
        with self.assertRaisesRegex(ValueError, "time zone"):
            self._load(start=pd.Timestamp("2024-02-01", tz="UTC"))
        with self.assertRaisesRegex(ValueError, "not a date"):
            self._load(start="not a date")

    # -- compatibility -------------------------------------------------------
    def test_an_unbounded_minute_load_still_loads_everything_but_warns(self):
        df, caught = self._load(symbols=["AAA"])
        self.assertEqual(sorted(self.repo.downloaded), sorted(self.frames))
        expected = self.full[self.full["symbol"] == "AAA"]
        self.assertEqual(len(df), len(expected))
        self.assertEqual(list(df.columns), list(expected.columns))
        minute = [w for w in caught if issubclass(w.category, ds.UnboundedMinuteLoadWarning)]
        self.assertEqual(len(minute), 1)
        self.assertIn("start=", str(minute[0].message))
        self.assertEqual(minute[0].filename, __file__)  # points at the caller

    def test_a_bounded_minute_load_does_not_warn(self):
        _, caught = self._load(symbols=["AAA"], start="2024-01-01", end="2024-01-31")
        self.assertFalse([w for w in caught if issubclass(w.category, ds.UnboundedMinuteLoadWarning)])

    def test_other_datasets_do_not_warn_and_old_loaders_keep_their_signature(self):
        calls = []

        def legacy(dataset_name, split, hf_token, symbols=None):  # no columns/window
            calls.append(dataset_name)
            return self.full.copy()

        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_load_dataset_from_hf", legacy), \
             warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            df = ds.load_dataset("Some-Weekly-Table")
        self.assertEqual(calls, ["Some-Weekly-Table"])
        self.assertEqual(len(df), len(self.full))
        self.assertFalse(caught)

    def test_is_minute_dataset(self):
        for name in ("Stocks-1Min-Price", "Cryptocurrencies-1Min-Price", "Forex-1Min-Price",
                     "paperswithbacktest/stocks-1min-price"):
            self.assertTrue(ds.is_minute_dataset(name), name)
        for name in ("Stocks-Daily-Price", "Options-Daily-Price", "Stocks-Weekly-ShortVolume"):
            self.assertFalse(ds.is_minute_dataset(name), name)

    # -- other layouts -------------------------------------------------------
    def test_undated_shard_names_are_all_read_with_a_warning(self):
        tmp = tempfile.mkdtemp()
        try:
            frames = {f"data/train-0000{i}-of-00003.parquet": f for i, f in enumerate(self.frames.values())}
            self.repo = _Repo(tmp, frames)
            df, caught = self._load(symbols=["AAA"], start="2024-02-10", end="2024-02-10")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(len(self.repo.downloaded), 3)
        self.assertEqual(len(df), 3)
        self.assertTrue(any("carry no period" in str(w.message) for w in caught))

    def test_the_subscriber_api_fetches_only_the_months_of_the_window(self):
        urls = [f"https://files.example/Test-1Min-Price/train-{m}.parquet?sig=s3cr3t" for m in MONTHS]
        local = dict(zip(urls, [os.path.join(self.tmp, f"data/train-{m}.parquet") for m in MONTHS]))
        fetched = []

        def http_get(url):
            fetched.append(url)
            with open(local[url], "rb") as fh:
                return fh.read()

        listing = mock.Mock()
        listing.json.return_value = {"files": urls}
        with mock.patch.object(ds, "_get_pwb_api_key", return_value="key"), \
             mock.patch.object(ds.requests, "get", return_value=listing), \
             mock.patch.object(ds, "_http_get", side_effect=http_get):
            df = ds.load_dataset("Test-1Min-Price", symbols=["CCC"], start="2024-03-10",
                                 end="2024-03-11", columns=["adj_close"])
        self.assertEqual(fetched, [urls[2]])
        self.assertEqual(len(df), 6)
        self.assertEqual(list(df.columns), ["symbol", "datetime", "adj_close"])

    def test_daily_price_tables_select_columns_after_adjustment(self):
        days = pd.date_range("2024-01-01", "2024-02-29", freq="D")
        daily = pd.DataFrame({
            "symbol": "AAA", "date": days.strftime("%Y-%m-%d"),
            "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "adj_close": 5.0, "volume": 1,
        })
        tmp = tempfile.mkdtemp()
        try:
            self.repo = _Repo(tmp, {
                "data/train-2024-01.parquet": daily[daily["date"] < "2024-02"],
                "data/train-2024-02.parquet": daily[daily["date"] >= "2024-02"],
            })
            df, _ = self._load("Stocks-Daily-Price", symbols=["AAA"], start="2024-02-03",
                               end="2024-02-05", columns=["close", "open"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(self.repo.downloaded, ["data/train-2024-02.parquet"])
        self.assertEqual(list(df.columns), ["symbol", "date", "close", "open"])
        self.assertEqual(list(df["close"]), [5.0, 5.0, 5.0])  # adjusted
        self.assertEqual(list(df["open"]), [5.0, 5.0, 5.0])


class WindowFilterTest(unittest.TestCase):
    """The pushed-down filter matches the type of the time column."""

    def _filter(self, table, **window):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.parquet")
            pq.write_table(table, path, row_group_size=2)
            return ds._read_one_parquet(path, window=ds._Window(**window))

    def test_timestamp_column(self):
        stamps = pd.to_datetime(["2024-01-01 23:59", "2024-01-02 00:00", "2024-01-02 23:59", "2024-01-03 00:00"])
        table = pa.table({"symbol": ["A"] * 4, "datetime": pa.array(stamps, pa.timestamp("ns")), "v": np.arange(4)})
        out = self._filter(table, start="2024-01-02", end="2024-01-02")
        self.assertEqual(list(out["v"]), [1, 2])

    def test_timestamp_column_with_a_time_zone(self):
        stamps = pd.to_datetime(["2024-01-01 23:59", "2024-01-02 00:00", "2024-01-03 00:00"]).tz_localize("UTC")
        table = pa.table({"symbol": ["A"] * 3, "datetime": pa.array(stamps), "v": np.arange(3)})
        out = self._filter(table, start="2024-01-02", end="2024-01-02")
        self.assertEqual(list(out["v"]), [1])

    def test_date_column_keeps_whole_days(self):
        days = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]).date
        table = pa.table({"symbol": ["A"] * 3, "date": pa.array(days, pa.date32()), "v": np.arange(3)})
        out = self._filter(table, start="2024-01-02 15:00", end="2024-01-02 18:00")
        self.assertEqual(list(out["v"]), [1])

    def test_string_timestamps_with_a_T_separator(self):
        table = pa.table({"symbol": ["A"] * 3,
                          "datetime": ["2024-01-01T23:59:00", "2024-01-02T09:30:00", "2024-01-03T00:00:00"],
                          "v": np.arange(3)})
        out = self._filter(table, start="2024-01-02", end="2024-01-02")
        self.assertEqual(list(out["v"]), [1])

    def test_no_time_column_is_an_error(self):
        table = pa.table({"symbol": ["A"], "v": [1]})
        with self.assertRaisesRegex(ValueError, "'datetime' or 'date' column"):
            self._filter(table, start="2024-01-02")


if __name__ == "__main__":
    unittest.main()
