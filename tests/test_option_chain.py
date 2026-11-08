"""load_option_chain reads one chain over a window, never the whole option table.

The shards are built here in the published layout (monthly files, rows sorted by
underlying then date, small row groups) and served from disk through a file
object that counts the bytes it hands out, standing in for HTTP range requests.
"""

import io
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import options as opt

UNDERLYINGS = [f"U{i:03d}" for i in range(400)] + ["AAPL", "SPY"]


def _month_table(month: str) -> pa.Table:
    """A month in the published layout; random prices so that it does not compress away."""
    rng = np.random.default_rng(int(month.replace("-", "")))
    days = pd.bdate_range(f"{month}-01", pd.Period(month).end_time.normalize()).strftime("%Y-%m-%d")
    unds = sorted(UNDERLYINGS)
    strikes = np.array([90.0, 100.0, 110.0])
    und, day, strike, cp = (a.ravel() for a in np.meshgrid(unds, days, strikes, ["C", "P"], indexing="ij"))
    n = len(und)
    frame = pd.DataFrame({
        "symbol": [f"{u}{month[2:4]}{month[5:7]}20{c}{int(k * 1000):08d}" for u, c, k in zip(und, cp, strike)],
        "date": day,
        "underlying": und,
        "expiration": f"{month}-20",
        "strike": strike,
        "option_type": np.where(cp == "C", "call", "put"),
        "close": rng.random(n) * 10,
        "volume": rng.integers(1, 1000, n),
        "implied_volatility": rng.random(n),
    }).sort_values(["underlying", "date", "symbol"])
    return pa.Table.from_pandas(frame, preserve_index=False)


class CountingFile(io.FileIO):
    opened = []

    def __init__(self, path):
        super().__init__(path, "rb")
        self.bytes_read = 0
        CountingFile.opened.append(os.path.basename(path))

    def read(self, n=-1):
        data = super().read(n)
        self.bytes_read += len(data)
        return data

    def readinto(self, buffer):
        n = super().readinto(buffer)
        self.bytes_read += n or 0
        return n


class OptionChainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {}
        for month in ("2024-01", "2024-02", "2024-03", "2024-04"):
            path = os.path.join(cls.tmp.name, f"train-{month}.parquet")
            pq.write_table(_month_table(month), path, row_group_size=5_000)
            cls.paths[f"data/train-{month}.parquet"] = path
        cls.sizes = {k: os.path.getsize(v) for k, v in cls.paths.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        CountingFile.opened = []
        self.handles = []
        sources = [(name, path, {}) for name, path in self.paths.items()] + [("README.md", "unused", {})]

        def _open(url, headers):
            handle = CountingFile(url)
            self.handles.append(handle)
            return handle

        self.patches = [
            mock.patch.object(opt, "_hf_sources", return_value=sources),
            mock.patch.object(opt, "_open", side_effect=_open),
            mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x", "PWB_API_KEY": ""}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for h in self.handles:
            h.close()
        for p in reversed(self.patches):
            p.stop()

    def test_underlyings_and_window_are_required(self):
        for kwargs in ({"underlyings": None, "start": "2024-01-01", "end": "2024-01-31"},
                       {"underlyings": [], "start": "2024-01-01", "end": "2024-01-31"},
                       {"underlyings": ["SPY"], "start": None, "end": "2024-01-31"},
                       {"underlyings": ["SPY"], "start": "2024-01-01", "end": None},
                       {"underlyings": ["SPY"], "start": "2024-02-01", "end": "2024-01-31"}):
            with self.assertRaises(ValueError):
                ds.load_option_chain(**kwargs)
        self.assertEqual(self.handles, [])

    def test_only_the_months_of_the_window_are_opened(self):
        df = ds.load_option_chain("SPY", "2024-02-10", "2024-03-05", verbose=False)
        self.assertEqual(sorted(CountingFile.opened), ["train-2024-02.parquet", "train-2024-03.parquet"])
        self.assertEqual(set(df["underlying"]), {"SPY"})
        self.assertGreaterEqual(min(df["date"]), date(2024, 2, 10))
        self.assertLessEqual(max(df["date"]), date(2024, 3, 5))
        self.assertIsInstance(df["expiration"].iloc[0], date)

    def test_rows_match_a_full_read_filtered_afterwards(self):
        df = ds.load_option_chain(["spy", "AAPL"], "2024-01-01", "2024-04-30", verbose=False)
        full = pd.concat(pq.read_table(p).to_pandas() for p in self.paths.values())
        full = full[full["underlying"].isin(["SPY", "AAPL"])]
        self.assertEqual(len(df), len(full))
        self.assertEqual(set(df["symbol"]), set(full["symbol"]))

    def test_one_chain_reads_a_small_part_of_each_month(self):
        ds.load_option_chain("AAPL", "2024-01-01", "2024-01-31", verbose=False)
        (handle,) = self.handles
        self.assertLess(handle.bytes_read, 0.15 * self.sizes["data/train-2024-01.parquet"])

    def test_columns_are_chosen_and_keys_always_come(self):
        df = ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", columns=["strike", "close"], verbose=False)
        self.assertEqual(list(df.columns), ["symbol", "date", "underlying", "strike", "close"])
        with self.assertRaises(ValueError):
            ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", columns=["bid"], verbose=False)

    def test_fewer_columns_fewer_bytes(self):
        ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", verbose=False)
        ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", columns=["close"], verbose=False)
        everything, narrow = self.handles
        self.assertLess(narrow.bytes_read, everything.bytes_read)

    def test_an_absent_underlying_is_an_empty_frame(self):
        with self.assertWarnsRegex(UserWarning, "No row for NOPE"):
            df = ds.load_option_chain("NOPE", "2024-01-01", "2024-01-31", columns=["close"], verbose=False)
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ["symbol", "date", "underlying", "close"])

    def test_load_dataset_refuses_the_whole_table(self):
        with mock.patch.object(ds, "_load_dataset_from_hf") as hf, mock.patch.object(ds, "_load_dataset_from_pwb") as pwb:
            for spelling in ("Options-Daily-Price", "options-daily-price", "OPTIONS-DAILY-PRICE",
                             " Options-Daily-Price ", "paperswithbacktest/Options-Daily-Price"):
                with self.assertRaises(ValueError, msg=spelling):
                    ds.load_dataset(spelling)
        hf.assert_not_called()
        pwb.assert_not_called()


class RangeFileTest(unittest.TestCase):
    """The HTTP file object asks for byte ranges and nothing more."""

    def _session(self, payload: bytes):
        session = mock.Mock()

        def get(url, headers=None, timeout=None, stream=False):
            lo, hi = headers["Range"].split("=")[1].split("-")
            if lo == "":
                lo, hi = max(len(payload) - int(hi), 0), len(payload) - 1
            else:
                lo, hi = int(lo), min(int(hi), len(payload) - 1)
            resp = mock.Mock(status_code=206, content=payload[lo:hi + 1],
                             headers={"Content-Range": f"bytes {lo}-{hi}/{len(payload)}"})
            resp.raise_for_status = lambda: None
            return resp

        session.get.side_effect = get
        return session

    def test_parquet_footer_and_row_group_are_read_by_range(self):
        buf = io.BytesIO()
        pq.write_table(_month_table("2024-01"), buf, row_group_size=5_000)
        payload = buf.getvalue()
        handle = opt.RangeFile("https://example/x.parquet", {"Authorization": "Bearer t"},
                               session=self._session(payload))
        table = opt._read_shard(handle, ["SPY"], date(2024, 1, 1), date(2024, 1, 31), ["close"])
        self.assertGreater(table.num_rows, 0)
        self.assertLess(handle.bytes_read, 0.15 * len(payload))
        sent = handle.session.get.call_args_list[0].kwargs["headers"]
        self.assertEqual(sent["Authorization"], "Bearer t")
        self.assertTrue(sent["Range"].startswith("bytes="))

    def test_a_server_ignoring_range_is_an_error_not_a_full_download(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(status_code=200, content=b"x" * 10, headers={})
        handle = opt.RangeFile("https://example/x.parquet", session=session)
        with self.assertRaises(OSError):
            handle.read(5)
        self.assertTrue(session.get.call_args.kwargs["stream"])
        session.get.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
