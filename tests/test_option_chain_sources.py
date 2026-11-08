"""load_option_chain never answers an empty frame for a reason it could name.

Measured on 2026-11-08 with a subscriber key (0.1.46): the data API listed the
149 monthly shards as ``0.parquet`` … ``148.parquet`` and served whole files to
range requests. The loader matched no name and returned an empty DataFrame,
without a word. These tests serve shards from a real local HTTP server, with
and without byte-range support, under monthly and positional names.
"""

import io
import os
import re
import tempfile
import threading
import unittest
import warnings
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pandas as pd
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import options as opt
from test_option_chain import _month_table

MONTHS = ("2024-01", "2024-02", "2024-03", "2024-04")


class _Handler(BaseHTTPRequestHandler):
    """Serves ``server.files`` (name -> bytes); honours Range when ``server.ranges``."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        name = self.path.split("?", 1)[0].lstrip("/")
        self.server.log.append((name, self.headers.get("Range")))
        body = self.server.files.get(name)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        size = len(body)
        m = re.match(r"^bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if self.server.ranges and m:
            lo, hi = m.groups()
            if lo == "":
                lo, hi = max(size - int(hi), 0), size - 1
            else:
                lo, hi = int(lo), min(int(hi) if hi else size - 1, size - 1)
            part = body[lo:hi + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {lo}-{hi}/{size}")
            self.send_header("Content-Length", str(len(part)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(part)
            return
        # What the API did before data-api #59: the whole file, as a 200.
        self.send_response(200)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class _Server:
    def __init__(self, files, ranges=True):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.files, self.httpd.ranges, self.httpd.log = files, ranges, []
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    @property
    def log(self):
        return self.httpd.log

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _shards() -> dict:
    out = {}
    for month in MONTHS:
        buf = io.BytesIO()
        pq.write_table(_month_table(month), buf, row_group_size=5_000)
        out[month] = buf.getvalue()
    return out


class SourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shards = _shards()

    def setUp(self):
        self.servers = []
        self.env = mock.patch.dict(os.environ, {"PWB_API_KEY": "pwbd_secret", "HF_ACCESS_TOKEN": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for server in self.servers:
            server.close()

    def _serve(self, positional: bool, ranges: bool):
        """A server holding the four months, named by month or by position."""
        files = {(f"{i}.parquet" if positional else f"train-{m}.parquet"): body
                 for i, (m, body) in enumerate(self.shards.items())}
        server = _Server(files, ranges=ranges)
        self.servers.append(server)
        # As the API lists them: the caller's key in each URL's query string.
        sources = [(name, f"{server.base}/{name}?pwb_api_key=pwbd_secret", {}) for name in sorted(files)]
        return server, sources

    def _expected(self, underlying, start, end):
        full = pd.concat(pq.read_table(io.BytesIO(b)).to_pandas() for b in self.shards.values())
        keep = (full["underlying"] == underlying) & (full["date"] >= start) & (full["date"] <= end)
        return full[keep]

    # -- names -------------------------------------------------------------
    def test_monthly_names_through_a_range_server_read_only_the_window(self):
        server, sources = self._serve(positional=False, ranges=True)
        with mock.patch.object(opt, "_pwb_sources", return_value=sources):
            df = ds.load_option_chain("SPY", "2024-02-10", "2024-03-05", columns=["close"], verbose=False)
        self.assertEqual(len(df), len(self._expected("SPY", "2024-02-10", "2024-03-05")))
        self.assertEqual({name for name, _ in server.log}, {"train-2024-02.parquet", "train-2024-03.parquet"})
        self.assertTrue(all(r and r.startswith("bytes=") for _, r in server.log))

    def test_positional_names_are_sorted_by_their_footers(self):
        """What the API served on 2026-11-08, once it answers ranges: the same
        rows as with monthly names, one footer request for each file outside
        the window, and a warning saying why it is slower."""
        server, sources = self._serve(positional=True, ranges=True)
        with mock.patch.object(opt, "_pwb_sources", return_value=sources):
            with self.assertWarnsRegex(UserWarning, "carry no month in their names"):
                df = ds.load_option_chain("SPY", "2024-02-10", "2024-03-05", columns=["close"], verbose=False)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), len(self._expected("SPY", "2024-02-10", "2024-03-05")))
        self.assertGreaterEqual(min(df["date"]), date(2024, 2, 10))
        self.assertLessEqual(max(df["date"]), date(2024, 3, 5))
        per_file = {}
        for name, _ in server.log:
            per_file[name] = per_file.get(name, 0) + 1
        # Months outside the window: their footer and nothing else.
        self.assertEqual(per_file["0.parquet"], 1)
        self.assertEqual(per_file["3.parquet"], 1)
        self.assertGreater(per_file["1.parquet"], 1)

    def test_an_empty_file_list_is_an_error(self):
        with mock.patch.object(opt, "_pwb_sources", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "lists no file"):
                ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", verbose=False)

    def test_a_window_outside_the_table_warns_with_what_it_covers(self):
        _, sources = self._serve(positional=False, ranges=True)
        with mock.patch.object(opt, "_pwb_sources", return_value=sources):
            with self.assertWarnsRegex(UserWarning, r"covers 2024-01\.\.2024-04"):
                df = ds.load_option_chain("SPY", "2019-01-01", "2019-12-31", verbose=False)
        self.assertTrue(df.empty)

    # -- ranges ------------------------------------------------------------
    def test_an_api_ignoring_ranges_is_an_explicit_error_without_the_key(self):
        server, sources = self._serve(positional=False, ranges=False)
        with mock.patch.object(opt, "_pwb_sources", return_value=sources):
            with self.assertRaises(opt.RangeNotSupportedError) as caught:
                ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", verbose=False)
        message = str(caught.exception)
        self.assertIn("HF_ACCESS_TOKEN", message)
        self.assertIn("whole file", message)
        self.assertNotIn("pwbd_secret", message)
        self.assertEqual(len(server.log), 1)  # refused on the first answer

    def test_an_api_ignoring_ranges_falls_back_to_the_hub_with_a_warning(self):
        _, api_sources = self._serve(positional=True, ranges=False)
        _, hub_sources = self._serve(positional=False, ranges=True)
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "hf_x"}), \
                mock.patch.object(opt, "_pwb_sources", return_value=api_sources), \
                mock.patch.object(opt, "_hf_sources", return_value=hub_sources) as hub:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                df = ds.load_option_chain("AAPL", "2024-01-01", "2024-01-31", verbose=False)
        hub.assert_called_once_with("hf_x")
        self.assertTrue(any("does not serve byte ranges" in str(w.message) for w in caught))
        self.assertEqual(len(df), len(self._expected("AAPL", "2024-01-01", "2024-01-31")))

    def test_the_hub_ignoring_ranges_is_not_retried_elsewhere(self):
        _, sources = self._serve(positional=False, ranges=False)
        with mock.patch.dict(os.environ, {"PWB_API_KEY": "", "HF_ACCESS_TOKEN": "hf_x"}), \
                mock.patch.object(opt, "_hf_sources", return_value=sources):
            with self.assertRaises(opt.RangeNotSupportedError):
                ds.load_option_chain("SPY", "2024-01-01", "2024-01-31", verbose=False)

    def test_the_footer_and_the_size_come_in_one_request(self):
        server, sources = self._serve(positional=False, ranges=True)
        handle = opt.RangeFile(sources[0][1])
        meta = pq.ParquetFile(handle).metadata
        self.assertGreater(meta.num_rows, 0)
        self.assertEqual(server.log, [("train-2024-01.parquet", f"bytes=-{opt._TAIL_BYTES}")])
        self.assertEqual(handle.size, len(self.shards["2024-01"]))


class PwbSourcesTest(unittest.TestCase):
    def test_every_listed_file_is_kept_and_the_key_travels_in_a_header(self):
        listed = [f"https://data.paperswithbacktest.com/v1/datasets/Options-Daily-Price/parquet/default/train/{i}.parquet"
                  f"?pwb_api_key=k" for i in range(3)]
        resp = mock.Mock(ok=True, status_code=200)
        resp.json.return_value = {"files": listed}
        with mock.patch.object(opt.requests, "get", return_value=resp) as get:
            sources = opt._pwb_sources("pwbd_secret")
        self.assertEqual([name for name, _, _ in sources], ["0.parquet", "1.parquet", "2.parquet"])
        self.assertEqual(get.call_args.kwargs["headers"], {"pwb-api-key": "pwbd_secret"})
        self.assertNotIn("pwb_api_key", get.call_args.kwargs["params"])

    def test_a_refused_listing_does_not_print_the_key(self):
        resp = mock.Mock(ok=False, status_code=403, text='{"error":"Invalid PWB-API-Key"}')
        with mock.patch.object(opt.requests, "get", return_value=resp):
            with self.assertRaises(opt.requests.exceptions.HTTPError) as caught:
                opt._pwb_sources("pwbd_secret")
        self.assertNotIn("pwbd_secret", str(caught.exception))


class HubFileListTest(unittest.TestCase):
    def test_a_split_mixing_layouts_is_read_from_its_dated_shards(self):
        """All-Daily-News on 2026-11-08: six stale ``-of-00006`` files from the
        previous layout and the 57 monthly files that replaced them, holding the
        same rows; reading both doubled every row from 2022-03 to 2026-06."""
        files = ["README.md", "data/train-00000-of-00002.parquet", "data/train-00001-of-00002.parquet",
                 "data/train-2022-03.parquet", "data/train-2026-11.parquet", "data/test-2024-01.parquet"]
        self.assertEqual(ds._list_hf_split_parquet_files(files, "train"),
                         ["data/train-2022-03.parquet", "data/train-2026-11.parquet"])

    def test_numbered_and_single_layouts_are_unchanged(self):
        self.assertEqual(ds._list_hf_split_parquet_files(
            ["data/train-00001-of-00002.parquet", "data/train-00000-of-00002.parquet"], "train"),
            ["data/train-00000-of-00002.parquet", "data/train-00001-of-00002.parquet"])
        self.assertEqual(ds._list_hf_split_parquet_files(["data/train.parquet"], "train"), ["data/train.parquet"])
        self.assertEqual(ds._list_hf_split_parquet_files(["data/train-2010.parquet", "data/train-2011.parquet"], "train"),
                         ["data/train-2010.parquet", "data/train-2011.parquet"])


if __name__ == "__main__":
    unittest.main()
