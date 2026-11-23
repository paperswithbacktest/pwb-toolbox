"""The disk cache of option shard bytes (option_cache): exact, keyed by revision, off when it must be.

Shards in the published layout are served by a real local HTTP server that
honours byte ranges and logs every request, as the Hub would at a fixed revision.
"""

import glob
import io
import multiprocessing
import os
import shutil
import tempfile
import unittest
from unittest import mock

import pandas as pd
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import option_cache as oc
from pwb_toolbox.datasets import options as opt
from pwb_toolbox.datasets import prepared_cache
from test_option_chain import _month_table
from test_option_chain_sources import _Server

MONTHS = ("2024-01", "2024-02", "2024-03")
SHA1, SHA2 = "1" * 40, "2" * 40
COLS = ["expiration", "strike", "option_type", "close", "volume"]


def _shards(months=MONTHS, salt=0):
    out = {}
    for month in months:
        table = _month_table(month)
        if salt:  # another revision: same layout, other prices
            df = table.to_pandas()
            df["close"] = df["close"] + salt
            import pyarrow as pa
            table = pa.Table.from_pandas(df, preserve_index=False)
        buf = io.BytesIO()
        pq.write_table(table, buf, row_group_size=2_000)
        out[f"data/train-{month}.parquet"] = buf.getvalue()
    return out


class _Hub:
    """Patches the Hub side of ``_hf_sources``: the revision, the file list and the URLs."""

    def __init__(self, server, revisions):
        self.server, self.revisions, self.sha = server, revisions, SHA1

    def snapshot(self, repo_id, token):
        prepared_cache.note_revision("hub", repo_id, self.sha)
        return self.sha, sorted(self.revisions[self.sha])

    def url(self, repo_id, filename, repo_type=None, revision=None):
        return f"{self.server.base}/{revision}/{filename}"

    def __enter__(self):
        self.patches = [
            mock.patch.object(ds, "_hub_snapshot", self.snapshot),
            mock.patch("huggingface_hub.hf_hub_url", self.url),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


def _load(underlyings="SPY", start="2024-01-10", end="2024-03-05", columns=COLS):
    return ds.load_option_chain(underlyings, start, end, columns=columns, verbose=False)


class OptionCacheTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.revisions = {SHA1: _shards(), SHA2: _shards(salt=1000)}
        files = {f"{sha}/{name}": body for sha, shards in cls.revisions.items() for name, body in shards.items()}
        cls.server = _Server(files, ranges=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pwb-optcache-")
        self.env = mock.patch.dict(os.environ, {
            "PWB_API_KEY": "", "HF_ACCESS_TOKEN": "hf_x", "PWB_CACHE": "1", "PWB_CACHE_DIR": self.dir,
            "PWB_OPTIONS_CACHE": "1", "PWB_HF_OFFLINE": "0", "HF_HUB_OFFLINE": "0"})
        self.env.start()
        self.block = mock.patch.object(oc, "BLOCK_SIZE", 16 * 1024)  # several blocks per row group
        self.block.start()
        prepared_cache.reset_process_state()
        oc.reset_stats()
        oc._IDENTITIES.clear()
        ds._HUB_LOCAL_FALLBACK.clear()
        self.hub = _Hub(self.server, self.revisions).__enter__()
        self.server.log.clear()

    def tearDown(self):
        self.hub.__exit__()
        self.block.stop()
        self.env.stop()
        prepared_cache.reset_process_state()
        ds._HUB_LOCAL_FALLBACK.clear()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _plain(self, **kw):
        with mock.patch.dict(os.environ, {"PWB_CACHE": "0"}):
            return _load(**kw)

    def _entries(self):
        return [p for p in glob.glob(os.path.join(self.dir, "options", "**", "*"), recursive=True)
                if os.path.isfile(p)]

    def assertSameFrame(self, a, b):
        pd.testing.assert_frame_equal(a, b, check_exact=True)
        self.assertEqual(list(a.dtypes), list(b.dtypes))

    # -- exactness ---------------------------------------------------------
    def test_cold_and_warm_reads_equal_the_uncached_read_bit_for_bit(self):
        ref = self._plain()
        self.assertFalse(self._entries())
        self.server.log.clear()
        cold = _load()
        self.assertSameFrame(cold, ref)
        self.assertTrue(self._entries())
        self.server.log.clear()
        warm = _load()
        self.assertSameFrame(warm, ref)
        self.assertEqual(self.server.log, [])  # footers and row groups all from disk
        self.assertGreater(oc.stats["block_hits"], 0)
        self.assertGreater(oc.stats["meta_hits"], 0)
        # The close column, byte for byte.
        self.assertEqual(warm["close"].to_numpy().tobytes(), ref["close"].to_numpy().tobytes())

    def test_other_columns_and_underlyings_reuse_the_blocks_they_share(self):
        _load()
        fetched = oc.stats["bytes_fetched"]
        ref = self._plain(underlyings=["AAPL", "SPY", "U001"], columns=["close", "implied_volatility"])
        oc.reset_stats()
        got = _load(underlyings=["AAPL", "SPY", "U001"], columns=["close", "implied_volatility"])
        self.assertSameFrame(got, ref)
        self.assertGreater(oc.stats["block_hits"], 0)
        self.assertLess(oc.stats["bytes_fetched"], fetched * 3)

    def test_all_columns_and_a_whole_month(self):
        ref = self._plain(underlyings=[f"U{i:03d}" for i in range(0, 400, 7)], start="2024-02-01",
                          end="2024-02-29", columns=None)
        _load(underlyings=[f"U{i:03d}" for i in range(0, 400, 7)], start="2024-02-01", end="2024-02-29", columns=None)
        got = _load(underlyings=[f"U{i:03d}" for i in range(0, 400, 7)], start="2024-02-01", end="2024-02-29",
                    columns=None)
        self.assertSameFrame(got, ref)

    # -- keys --------------------------------------------------------------
    def test_a_new_revision_is_read_again_and_gives_its_own_rows(self):
        first = _load()
        self.hub.sha = SHA2
        ds._HUB_SNAPSHOTS.pop(opt.REPO_ID, None)
        self.server.log.clear()
        second = _load()
        self.assertTrue(self.server.log)  # nothing of SHA1 served for SHA2
        self.assertTrue(all(path.startswith(f"/{SHA2}/") for path, _ in
                            [("/" + name, r) for name, r in self.server.log]))
        self.assertSameFrame(second, self._plain())
        self.assertFalse((first["close"].to_numpy() == second["close"].to_numpy()).any())
        # Back to the first revision: its blocks are still there, nothing fetched.
        self.hub.sha = SHA1
        self.server.log.clear()
        again = _load()
        self.assertEqual(self.server.log, [])
        self.assertSameFrame(again, first)

    # -- off ---------------------------------------------------------------
    def _assert_off(self):
        ref = self._plain()
        self.server.log.clear()
        got = _load()
        self.assertSameFrame(got, ref)
        self.assertEqual(self._entries(), [])
        self.assertTrue(self.server.log)

    def test_pwb_cache_0_turns_it_off(self):
        with mock.patch.dict(os.environ, {"PWB_CACHE": "0"}):
            self._assert_off()

    def test_pwb_options_cache_0_turns_it_off(self):
        with mock.patch.dict(os.environ, {"PWB_OPTIONS_CACHE": "0"}):
            self._assert_off()

    def test_a_degraded_process_neither_reads_nor_writes(self):
        _load()  # fill the cache
        before = sorted(self._entries())
        prepared_cache.note_degraded("cost table unreadable (test)")
        self.server.log.clear()
        oc.reset_stats()
        got = _load()
        self.assertTrue(self.server.log)  # read from the network, not from disk
        self.assertEqual(oc.stats["block_hits"] + oc.stats["meta_hits"] + oc.stats["stored"], 0)
        self.assertEqual(sorted(self._entries()), before)
        self.assertSameFrame(got, self._plain())

    def test_offline_and_local_snapshot_fallback_turn_it_off(self):
        _load()
        for env in ({"HF_HUB_OFFLINE": "1"}, {"PWB_HF_OFFLINE": "1"}):
            with mock.patch.dict(os.environ, env):
                self.assertFalse(oc.active(opt.REPO_ID))
                self.assertIsInstance(opt._open(next(iter(oc._IDENTITIES)), {}), opt.RangeFile)
                self.assertNotIsInstance(opt._open(next(iter(oc._IDENTITIES)), {}), opt._CachedRangeFile)
        ds._HUB_LOCAL_FALLBACK.add(opt.REPO_ID)
        self.assertFalse(oc.active(opt.REPO_ID))
        oc.reset_stats()
        self.server.log.clear()
        _load()
        self.assertTrue(self.server.log)
        self.assertEqual(oc.stats["block_hits"] + oc.stats["meta_hits"], 0)

    def test_a_network_failure_is_raised_as_without_the_cache_and_stores_nothing(self):
        self.hub.sha = "f" * 40  # the server has no file at this revision: 404
        self.revisions["f" * 40] = self.revisions[SHA1]
        try:
            with self.assertRaises(Exception) as cached_exc:
                _load()
            with self.assertRaises(Exception) as plain_exc:
                self._plain()
        finally:
            del self.revisions["f" * 40]
        self.assertEqual(type(cached_exc.exception), type(plain_exc.exception))
        self.assertEqual(self._entries(), [])

    def test_api_files_without_a_revision_are_not_cached(self):
        sources = [(name, f"{self.server.base}/{SHA1}/{name}", {}) for name in sorted(self.revisions[SHA1])]
        with mock.patch.dict(os.environ, {"PWB_API_KEY": "pwbd_x"}), \
                mock.patch.object(opt, "_pwb_sources", return_value=sources):
            _load()
            _load()
        self.assertEqual(self._entries(), [])

    # -- files -------------------------------------------------------------
    def test_a_corrupt_or_truncated_entry_is_dropped_and_fetched_again(self):
        ref = _load()
        blocks = sorted(glob.glob(os.path.join(self.dir, "options", "**", "*.blk"), recursive=True))
        with open(blocks[0], "r+b") as fh:
            fh.seek(40)
            fh.write(b"\xff\xff\xff\xff")
        with open(blocks[1], "r+b") as fh:
            fh.truncate(10)
        oc.reset_stats()
        got = _load()
        self.assertSameFrame(got, ref)
        self.assertGreaterEqual(oc.stats["errors"], 2)
        self.assertGreaterEqual(oc.stats["block_misses"], 2)

    def test_the_size_cap_evicts_least_recently_used(self):
        with mock.patch.dict(os.environ, {"PWB_OPTIONS_CACHE_MAX_GB": str(100 * 1024 / 1024**3)}):
            oc._written_since_scan[0] = None
            got = _load()
            oc.evict(oc.cache_root())
            total = sum(os.path.getsize(p) for p in self._entries())
        self.assertLessEqual(total, 100 * 1024)
        self.assertSameFrame(got, self._plain())

    def test_concurrent_writers_never_leave_a_torn_or_temporary_file(self):
        ref = self._plain()
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(3) as pool:
            results = pool.map(_worker, [(self.server.base, self.dir, k) for k in range(6)])
        for frame_bytes in results:
            self.assertEqual(frame_bytes, _frame_bytes(ref))
        self.assertEqual(glob.glob(os.path.join(self.dir, "options", "**", ".tmp-*"), recursive=True), [])
        for path in self._entries():
            self.assertIsNotNone(oc._read_entry(path), path)


def _frame_bytes(df):
    return pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes() + str(list(df.dtypes)).encode()


def _worker(args):
    """One process: loads the same chains repeatedly, deleting entries now and then."""
    base, cache_dir, k = args
    import random
    os.environ.update({"PWB_API_KEY": "", "HF_ACCESS_TOKEN": "hf_x", "PWB_CACHE": "1", "PWB_CACHE_DIR": cache_dir,
                       "PWB_OPTIONS_CACHE": "1", "PWB_HF_OFFLINE": "0", "HF_HUB_OFFLINE": "0"})
    oc.BLOCK_SIZE = 16 * 1024

    class S:
        pass
    server = S()
    server.base = base
    hub = _Hub(server, {SHA1: _shards()})
    rng = random.Random(k)
    out = None
    with hub:
        for i in range(5):
            df = _load()
            current = _frame_bytes(df)
            if out is not None and current != out:
                return b"MISMATCH"
            out = current
            entries = glob.glob(os.path.join(cache_dir, "options", "**", "*.blk"), recursive=True)
            for path in rng.sample(entries, min(len(entries), 3)):
                try:
                    os.unlink(path)
                except OSError:
                    pass
    return out


if __name__ == "__main__":
    unittest.main()
