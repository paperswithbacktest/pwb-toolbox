"""The subscriber API path: a disk cache keyed by content, parallel downloads.

Until 0.1.49 every call through ``data.paperswithbacktest.com`` downloaded every
shard again (7 ETFs: ~200 s and 328 MB at each call). The API, its file list and
the Hub's metadata are replaced by fakes reading parquet files from a temporary
directory: nothing touches the network.
"""

import contextlib
import io
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import hashlib

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds

NAME = "Test-Daily-Price"
MONTHS = ["2019-01", "2019-02", "2019-03", "2019-04"]
KEY = "s3cr3t-key"


def _month(month, scale=1.0):
    days = pd.bdate_range(f"{month}-01", periods=15)
    rows = []
    for i, symbol in enumerate(["AAA", "BBB", "CCC"]):
        rows.append(pd.DataFrame({
            "symbol": symbol, "date": days.strftime("%Y-%m-%d"),
            "close": scale * (10.0 + i + np.arange(len(days))), "volume": 100 + i,
        }))
    return pd.concat(rows, ignore_index=True)


class _FakeApi:
    """Files on disk; the API's list, the Hub's metadata and the downloads."""

    def __init__(self, root):
        self.root = root
        self.commit = "c1"
        self.downloads = []
        self.probes = []
        self.etags = {}
        self.truncate = set()
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.delay = 0.0
        for m in MONTHS:
            self.write(f"data/train-{m}.parquet", _month(m))

    def write(self, rel, df):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
        with open(path, "rb") as fh:
            self.etags[rel] = hashlib.md5(fh.read()).hexdigest()

    def rel(self, url):
        return url.split(f"/v1/datasets/{NAME}/", 1)[1].split("?", 1)[0]

    def listing(self, name, split, key, revision=None):
        assert key == KEY
        q = f"?revision={revision}&pwb_api_key={key}" if revision else f"?pwb_api_key={key}"
        return [f"https://data.paperswithbacktest.com/v1/datasets/{name}/data/train-{m}.parquet{q}"
                for m in MONTHS]

    def index(self, name):
        files = {}
        for m in MONTHS:
            rel = f"data/train-{m}.parquet"
            with open(os.path.join(self.root, rel), "rb") as fh:
                body = fh.read()
            files[rel] = (len(body), hashlib.sha256(body).hexdigest())
        return (self.commit, files)

    def probe(self, url):
        rel = self.rel(url)
        self.probes.append(rel)
        return self.etags[rel], os.path.getsize(os.path.join(self.root, rel))

    def download(self, url, fh):
        rel = self.rel(url)
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.downloads.append(rel)
        try:
            time.sleep(self.delay)
            with open(os.path.join(self.root, rel), "rb") as src:
                body = src.read()
            if rel in self.truncate:
                body = body[: len(body) // 2]
            fh.write(body)
            return len(body), hashlib.sha256(body).hexdigest()
        finally:
            with self.lock:
                self.active -= 1

    def http_get(self, url):
        rel = self.rel(url)
        self.downloads.append(rel)
        with open(os.path.join(self.root, rel), "rb") as fh:
            return fh.read()


class ApiCacheTest(unittest.TestCase):
    def setUp(self):
        self.files = tempfile.mkdtemp()
        self.cache = tempfile.mkdtemp()
        self.api = _FakeApi(self.files)
        ds._API_INDEXES.clear()
        ds._READ_MEMO.clear()

    def tearDown(self):
        ds._API_INDEXES.clear()
        ds._READ_MEMO.clear()
        shutil.rmtree(self.files, ignore_errors=True)
        shutil.rmtree(self.cache, ignore_errors=True)

    def _load(self, index=True, env=None, new_process=True, **kw):
        if new_process:  # what a second process starts from: nothing in memory
            ds._API_INDEXES.clear()
            ds._READ_MEMO.clear()
        self.api.downloads.clear()
        self.api.probes.clear()
        environ = {"PWB_CACHE_DIR": self.cache, "PWB_API_HUB_INDEX": "1", **(env or {})}
        with mock.patch.dict(os.environ, environ), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=KEY), \
             mock.patch.object(ds, "_api_listing", side_effect=self.api.listing), \
             mock.patch.object(ds, "_api_file_index", side_effect=self.api.index if index else (lambda n: None)), \
             mock.patch.object(ds, "_api_probe", side_effect=self.api.probe), \
             mock.patch.object(ds, "_http_download", side_effect=self.api.download), \
             mock.patch.object(ds, "_http_get", side_effect=self.api.http_get), \
             contextlib.redirect_stdout(io.StringIO()):
            return ds.load_dataset(NAME, **kw)

    def _blobs(self):
        d = os.path.join(self.cache, "api", "blobs")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def _reference(self, **kw):
        return self._load(env={"PWB_API_CACHE": "0"}, **kw)

    def test_second_call_downloads_nothing_and_returns_the_same_frame(self):
        reference = self._reference(symbols=["BBB"])
        self.assertEqual(len(self.api.downloads), 4)  # uncached: every file
        first = self._load(symbols=["BBB"])
        self.assertEqual(len(self.api.downloads), 4)
        second = self._load(symbols=["BBB"])
        self.assertEqual(self.api.downloads, [])
        self.assertEqual(self.api.probes, [])  # content-addressed: nothing to ask
        pd.testing.assert_frame_equal(reference, first)
        pd.testing.assert_frame_equal(reference, second)
        self.assertTrue(all(b.startswith("sha256-") for b in self._blobs()))
        self.assertFalse(any(KEY in b for b in self._blobs()))

    def test_a_new_commit_downloads_only_the_files_that_changed(self):
        self._load()
        self.api.commit = "c2"
        self.api.write("data/train-2019-03.parquet", _month("2019-03", scale=2.0))
        out = self._load()
        self.assertEqual(self.api.downloads, ["data/train-2019-03.parquet"])
        march = out[out["date"].astype(str).str.startswith("2019-03")]
        self.assertGreater(march["close"].min(), 19.0)

    def test_a_truncated_download_is_never_served_nor_kept(self):
        self.api.truncate.add("data/train-2019-02.parquet")
        with self.assertRaises(ds._CorruptDownload):
            self._load()
        self.assertFalse(any("2019-02" in b for b in self._blobs()))
        self.assertEqual(os.listdir(os.path.join(self.cache, "api", "tmp")), [])
        self.api.truncate.clear()
        pd.testing.assert_frame_equal(self._load(), self._reference())

    def test_a_cached_file_of_the_wrong_size_is_downloaded_again(self):
        self._load()
        blob = os.path.join(self.cache, "api", "blobs", self._blobs()[0])
        with open(blob, "r+b") as fh:
            fh.truncate(10)
        out = self._load()
        self.assertEqual(len(self.api.downloads), 1)
        pd.testing.assert_frame_equal(out, self._reference())

    def test_without_the_hub_metadata_the_etag_keys_the_cache(self):
        reference = self._reference()
        first = self._load(index=False)
        self.assertEqual(len(self.api.downloads), 4)
        second = self._load(index=False)
        self.assertEqual(self.api.downloads, [])
        self.assertEqual(len(self.api.probes), 4)
        pd.testing.assert_frame_equal(reference, first)
        pd.testing.assert_frame_equal(reference, second)
        self.assertTrue(all(b.startswith("etag-") for b in self._blobs()))
        self.api.write("data/train-2019-04.parquet", _month("2019-04", scale=3.0))
        self._load(index=False)
        self.assertEqual(self.api.downloads, ["data/train-2019-04.parquet"])

    def test_a_file_whose_version_cannot_be_told_is_not_cached(self):
        with mock.patch.object(ds, "_api_probe", return_value=None):
            self.api.downloads.clear()
            reference = self._reference()
            ds._API_INDEXES.clear()
            ds._READ_MEMO.clear()
            environ = {"PWB_CACHE_DIR": self.cache}
            with mock.patch.dict(os.environ, environ), \
                 mock.patch.object(ds, "_get_pwb_api_key", return_value=KEY), \
                 mock.patch.object(ds, "_api_listing", side_effect=self.api.listing), \
                 mock.patch.object(ds, "_api_file_index", return_value=None), \
                 mock.patch.object(ds, "_http_get", side_effect=self.api.http_get), \
                 contextlib.redirect_stdout(io.StringIO()):
                out = ds.load_dataset(NAME)
        pd.testing.assert_frame_equal(reference, out)
        self.assertEqual(self._blobs(), [])

    def test_the_window_bounds_the_download(self):
        self._load(start="2019-03-04", end="2019-03-08")
        self.assertEqual(self.api.downloads, ["data/train-2019-03.parquet"])

    def test_downloads_run_in_parallel_within_the_bound(self):
        self.api.delay = 0.05
        self._load(env={"PWB_API_WORKERS": "2"})
        self.assertEqual(self.api.peak, 2)
        shutil.rmtree(os.path.join(self.cache, "api"))
        self.api.peak = 0
        self._load(env={"PWB_API_WORKERS": "1"})
        self.assertEqual(self.api.peak, 1)

    def test_least_recently_used_files_are_evicted_first(self):
        size = os.path.getsize(os.path.join(self.files, "data/train-2019-01.parquet"))
        cap_gb = str(2.5 * size / 1024**3)
        self._load(start="2019-01-01", end="2019-02-20", env={"PWB_API_CACHE_MAX_GB": cap_gb})
        old = set(self._blobs())
        self.assertEqual(len(old), 2)
        time.sleep(0.02)
        self._load(start="2019-03-10", end="2019-04-30", env={"PWB_API_CACHE_MAX_GB": cap_gb})
        # the two files of this call are kept, the two older ones make room
        self.assertEqual(len(self._blobs()), 2)
        self.assertFalse(old & set(self._blobs()))

    def test_the_hub_path_is_untouched(self):
        with mock.patch.object(ds, "_load_dataset_from_hf", return_value=pd.DataFrame({"symbol": ["A"]})) as hf, \
             mock.patch.object(ds, "_api_fetch_all") as fetch, \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}):
            ds.load_dataset("Anything")
        hf.assert_called_once()
        fetch.assert_not_called()


class ApiHelpersTest(unittest.TestCase):
    def test_file_path_of_an_api_url(self):
        url = "https://data.paperswithbacktest.com/v1/datasets/X/data/train-2020-01.parquet?revision=abc&pwb_api_key=k"
        self.assertEqual(ds._api_file_path(url, "X"), ("data/train-2020-01.parquet", "abc"))
        conv = "https://data.paperswithbacktest.com/v1/datasets/X/parquet/default/train/0.parquet?pwb_api_key=k"
        self.assertEqual(ds._api_file_path(conv, "X"), (None, None))

    def test_probe_reads_etag_and_total_size(self):
        resp = mock.Mock(status_code=206, headers={"ETag": '"abc"', "Content-Range": "bytes 0-0/1234"})
        with mock.patch.object(ds.requests, "get", return_value=resp):
            self.assertEqual(ds._api_probe("https://x"), ("abc", 1234))
        resp = mock.Mock(status_code=206, headers={"Content-Range": "bytes 0-0/1234"})
        with mock.patch.object(ds.requests, "get", return_value=resp):
            self.assertIsNone(ds._api_probe("https://x"))

    def test_hub_index_reads_sizes_and_hashes_once(self):
        ds._API_INDEXES.clear()
        sib = mock.Mock(rfilename="data/train-2020-01.parquet", size=12, lfs={"sha256": "ab" * 32})
        readme = mock.Mock(rfilename="README.md", size=3, lfs=None)
        info = mock.Mock(sha="c0ffee", siblings=[sib, readme])
        with mock.patch.dict(os.environ, {"PWB_API_HUB_INDEX": "1", "PWB_HF_OFFLINE": "0", "HF_HUB_OFFLINE": "0"}), \
             mock.patch.object(ds, "HfApi") as api:
            api.return_value.dataset_info.return_value = info
            first = ds._api_file_index("Y")
            second = ds._api_file_index("Y")
        self.assertEqual(first, ("c0ffee", {"data/train-2020-01.parquet": (12, "ab" * 32)}))
        self.assertIs(first, second)
        self.assertEqual(api.return_value.dataset_info.call_count, 1)
        ds._API_INDEXES.clear()


if __name__ == "__main__":
    unittest.main()


class ThrottleTest(unittest.TestCase):
    """A 429 pauses every download of the process and is retried; an error never
    carries the API key."""

    def _response(self, status, body=b"x", headers=None):
        resp = mock.MagicMock(status_code=status, headers=headers or {})
        resp.__enter__.return_value = resp
        if status >= 400:
            err = ds.requests.exceptions.HTTPError(
                f"{status} Client Error for url: https://h/x?pwb_api_key=SECRET123&a=1", response=resp)
            resp.raise_for_status.side_effect = err
        else:
            resp.iter_content.return_value = [body]
        return resp

    def setUp(self):
        ds._API_GATE["until"] = 0.0

    def test_429_waits_at_the_gate_then_succeeds(self):
        answers = [self._response(429, headers={"Retry-After": "0"}), self._response(429), self._response(200, b"abc")]
        with mock.patch.object(ds.requests, "get", side_effect=answers), \
             mock.patch.object(ds, "_HTTP_429_WAIT_SECONDS", 0.01), \
             mock.patch.object(ds.time, "sleep"):
            buf = io.BytesIO()
            size, digest = ds._http_download("https://h/x?pwb_api_key=SECRET123", buf)
        self.assertEqual((size, buf.getvalue()), (3, b"abc"))
        self.assertEqual(digest, hashlib.sha256(b"abc").hexdigest())

    def test_errors_are_redacted(self):
        with mock.patch.object(ds.requests, "get", return_value=self._response(403)):
            with self.assertRaises(ds.requests.exceptions.HTTPError) as ctx:
                ds._http_download("https://h/x?pwb_api_key=SECRET123", io.BytesIO())
        self.assertNotIn("SECRET123", str(ctx.exception))
        answers = [self._response(429) for _ in range(ds._HTTP_429_ATTEMPTS)]
        with mock.patch.object(ds.requests, "get", side_effect=answers), \
             mock.patch.object(ds, "_HTTP_429_WAIT_SECONDS", 0.0), \
             mock.patch.object(ds.time, "sleep"):
            with self.assertRaises(ds.requests.exceptions.HTTPError) as ctx:
                ds._http_download("https://h/x?pwb_api_key=SECRET123", io.BytesIO())
        self.assertNotIn("SECRET123", str(ctx.exception))
        self.assertIn("429", str(ctx.exception))
