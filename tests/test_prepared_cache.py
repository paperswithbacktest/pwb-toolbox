"""The disk cache of prepared data (``pwb_toolbox.datasets.prepared_cache``).

What it must guarantee: a hit returns, bit for bit, what the computation
returns; a new revision of a dataset, a new version of the code or a degraded
process is a miss; two processes writing the same entry leave a whole file.
"""

import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import warnings
from contextlib import redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.backtesting.commission as commission
import pwb_toolbox.datasets as ds
from pwb_toolbox.datasets import prepared_cache as pc


def _fresh_process():
    """What a new process starts with: no revision, no memo, no table."""
    pc.reset_process_state()
    ds._HUB_SNAPSHOTS.clear()
    ds._READ_MEMO.clear()
    commission._PARAMS_CACHE = None
    commission._VINTAGE_CACHE = None
    commission._FUTURES_CACHE = None
    commission._CURRENCY_CACHE = None
    commission._UNIVERSE_CACHE = None
    commission._LAMBDA_CACHE = None


class _CacheTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._env = mock.patch.dict(os.environ, {"PWB_CACHE": "1", "PWB_CACHE_DIR": self.root})
        self._env.start()
        os.environ.pop("PWB_PIT_UNIVERSE_DIR", None)
        _fresh_process()

    def tearDown(self):
        self._env.stop()
        _fresh_process()
        self._tmp.cleanup()

    def entries(self):
        out = []
        for dirpath, _dirs, names in os.walk(self.root):
            out += [os.path.join(dirpath, n) for n in names if n.endswith(".pwbc")]
        return out


def _awkward_frame():
    """Every kind of column a prepared frame carries."""
    idx = pd.date_range("2020-01-01", periods=5, freq="D", name="date")
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["close", "open"]], names=["symbol", None])
    df = pd.DataFrame(np.arange(20, dtype="float64").reshape(5, 4) / 3.0, index=idx, columns=cols)
    df.iloc[1, 2] = np.nan
    df[("CCC", "close")] = [-0.0, np.inf, 1e-310, 2.5, np.nan]
    df[("DDD", "volume")] = np.arange(5, dtype="int64")
    df[("EEE", "when")] = [pd.Timestamp("2020-01-01").date()] * 5
    df[("FFF", "cat")] = pd.Categorical(list("abcab"))
    df.attrs["pwb_routes"] = ds._Routes({"AAA": "Stocks-Daily-Price"})
    return df


def _bits_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    for col in a.columns:
        x, y = a[col].to_numpy(), b[col].to_numpy()
        if x.dtype.kind == "f":
            if x.view(np.uint64).tobytes() != y.view(np.uint64).tobytes():
                return False
    return a.attrs == b.attrs and type(a.attrs.get("pwb_routes")) is type(b.attrs.get("pwb_routes"))


class FileFormatTest(_CacheTest):
    def test_a_frame_comes_back_bit_for_bit_and_writable(self):
        df = _awkward_frame()
        path = os.path.join(self.root, "x.pwbc")
        pc._dump(path, df, {"format": pc.FORMAT})
        back, header = pc._load(path)
        self.assertTrue(_bits_equal(df, back))
        self.assertEqual(list(back.dtypes), list(df.dtypes))
        # Mapped copy-on-write: the caller may write, the file does not change.
        back.iloc[0, 0] = 123.0
        again, _ = pc._load(path)
        self.assertEqual(again.iloc[0, 0], df.iloc[0, 0])

    def test_a_truncated_file_is_refused(self):
        path = os.path.join(self.root, "x.pwbc")
        pc._dump(path, _awkward_frame(), {"format": pc.FORMAT})
        with open(path, "r+b") as fh:
            fh.truncate(os.path.getsize(path) - 10)
        with self.assertRaises(Exception):
            pc._load(path)


def _cached_fn(sha_holder, calls, name="fake"):
    """A cached computation that reads one dataset at ``sha_holder[0]``."""

    @pc.cached(name)
    def compute(symbols, start="2020-01-01"):
        calls.append(symbols)
        pc.note_revision("hub", "paperswithbacktest/Fake", sha_holder[0])
        print(f"[costs] computed {symbols} at {sha_holder[0]}")
        return pd.DataFrame({"x": np.linspace(0, 1, 7) * len(calls)}, index=range(7))

    return compute


class DecoratorTest(_CacheTest):
    def setUp(self):
        super().setUp()
        self.sha = ["a" * 40]
        self.calls = []
        self.fn = _cached_fn(self.sha, self.calls)
        # The revision check asks the Hub through _hub_snapshot.
        self._snap = mock.patch.object(ds, "_hub_snapshot", side_effect=self._snapshot)
        self._snap.start()

    def tearDown(self):
        self._snap.stop()
        super().tearDown()

    def _snapshot(self, repo_id, token):
        pc.note_revision("hub", repo_id, self.sha[0])
        return self.sha[0], []

    def test_second_process_reads_the_entry_and_replays_the_prints(self):
        first = self.fn(["AAA"])
        _fresh_process()
        out = io.StringIO()
        with redirect_stdout(out):
            second = self.fn(["AAA"])
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(_bits_equal(first, second))
        self.assertIn("[costs] computed ['AAA']", out.getvalue())
        self.assertEqual(pc.stats["hits"], 1)

    def test_a_new_revision_of_the_dataset_is_recomputed(self):
        self.fn(["AAA"])
        _fresh_process()
        self.sha[0] = "b" * 40
        self.fn(["AAA"])
        self.assertEqual(len(self.calls), 2)
        # Both revisions are kept: going back to the first is a hit.
        _fresh_process()
        self.sha[0] = "a" * 40
        self.fn(["AAA"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.entries()), 2)

    def test_other_arguments_or_code_are_other_entries(self):
        self.fn(["AAA"])
        self.fn(["AAA"], start="2021-01-01")
        self.fn(("AAA",))
        self.assertEqual(len(self.calls), 3)
        _fresh_process()
        with mock.patch.object(pc, "_CODE_VERSION", "another version of the code"):
            self.fn(["AAA"])
        self.assertEqual(len(self.calls), 4)

    def test_pwb_settings_are_part_of_the_key(self):
        self.fn(["AAA"])
        with mock.patch.dict(os.environ, {"PWB_PIT_EXIT": "liquidate"}):
            self.fn(["AAA"])
        self.assertEqual(len(self.calls), 2)

    def test_off_with_pwb_cache_0(self):
        with mock.patch.dict(os.environ, {"PWB_CACHE": "0"}):
            self.fn(["AAA"])
            self.fn(["AAA"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.entries(), [])

    def test_an_unknown_revision_is_never_stored(self):
        pc.note_revision("api", "Some-Dataset", None)
        self.fn(["AAA"])
        self.assertEqual(self.entries(), [])

    def test_nothing_resolved_nothing_stored(self):
        @pc.cached("nothing")
        def compute():
            return 1

        compute()
        self.assertEqual(self.entries(), [])

    def test_a_degraded_process_neither_reads_nor_writes(self):
        self.fn(["AAA"])
        _fresh_process()
        pc.note_degraded("a cost table could not be read")
        self.fn(["AAA"])
        self.fn(["BBB"])
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(pc.stats["hits"], 0)
        self.assertEqual(len(self.entries()), 1)

    def test_only_the_outermost_call_is_cached(self):
        inner_calls = []

        @pc.cached("inner")
        def inner():
            inner_calls.append(1)
            pc.note_revision("hub", "paperswithbacktest/Fake", self.sha[0])
            return 2

        @pc.cached("outer")
        def outer():
            return inner() + 1

        self.assertEqual(outer(), 3)
        self.assertEqual(len(self.entries()), 1)
        _fresh_process()
        self.assertEqual(outer(), 3)
        self.assertEqual(len(inner_calls), 1)

    def test_a_corrupt_entry_is_recomputed(self):
        self.fn(["AAA"])
        (path,) = self.entries()
        with open(path, "r+b") as fh:
            fh.seek(10)
            fh.write(b"garbage")
        _fresh_process()
        self.fn(["AAA"])
        self.assertEqual(len(self.calls), 2)

    def test_pwb_warnings_are_raised_again_on_a_hit(self):
        @pc.cached("warns")
        def compute():
            pc.note_revision("hub", "paperswithbacktest/Fake", self.sha[0])
            ds._warn_unbounded_minute("Test-1Min-Price", ["AAA"])  # raised by pwb_toolbox code
            warnings.warn("the test's own warning is not the cache's business")
            return 1

        with warnings.catch_warnings(record=True) as first:
            warnings.simplefilter("always")
            compute()
        _fresh_process()
        with warnings.catch_warnings(record=True) as second:
            warnings.simplefilter("always")
            compute()
        self.assertEqual([w.category for w in first], [ds.UnboundedMinuteLoadWarning, UserWarning])
        self.assertEqual([(w.category, str(w.message)) for w in second],
                         [(w.category, str(w.message)) for w in first[:1]])

    def test_size_cap_evicts_the_least_recently_used(self):
        self.fn(["AAA"])
        (first,) = self.entries()
        cap = os.path.getsize(first) * 1.5 / 1024**3
        with mock.patch.dict(os.environ, {"PWB_PREPARED_CACHE_MAX_GB": repr(cap)}):
            self.fn(["BBB"])
        (kept,) = self.entries()
        self.assertNotEqual(kept, first)


def _write_table(path, values):
    pd.DataFrame({
        "symbol": ["AAA", "AAA", "BBB"],
        "date": ["2020-03-31", "2020-06-30", "2020-03-31"],
        "total_assets": values,
    }).to_parquet(path)


class LoadDatasetTest(_CacheTest):
    """``load_dataset`` end to end, on a fake Hub snapshot."""

    def setUp(self):
        super().setUp()
        self.files = {}
        self.sha = ["1" * 40]
        self.reads = []
        for sha, values in (("1" * 40, [1.0, 2.0, 3.0]), ("2" * 40, [1.0, 2.5, 3.0])):
            path = os.path.join(self.root, "hub", sha, "train.parquet")
            os.makedirs(os.path.dirname(path))
            _write_table(path, values)
            self.files[sha] = path
        real_read = ds._read_parquet_files

        def read(paths, *a, **k):
            self.reads.append(paths)
            return real_read(paths, *a, **k)

        def snapshot(repo_id, token):
            ds._HUB_SNAPSHOTS[repo_id] = (self.sha[0], ["data/train.parquet"])
            pc.note_revision("hub", repo_id, self.sha[0])
            return ds._HUB_SNAPSHOTS[repo_id]

        self._patches = [
            mock.patch.object(ds, "_hub_snapshot", side_effect=snapshot),
            mock.patch.object(ds, "hf_hub_download", side_effect=lambda **kw: self.files[kw["revision"]]),
            mock.patch.object(ds, "_read_parquet_files", side_effect=read),
            mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}),
        ]
        for p in self._patches:
            p.start()
        os.environ.pop("PWB_API_KEY", None)

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        super().tearDown()

    def test_hit_is_identical_and_reads_nothing(self):
        first = ds.load_dataset("Stocks-Quarterly-BalanceSheet", symbols=["AAA"])
        _fresh_process()
        second = ds.load_dataset("Stocks-Quarterly-BalanceSheet", symbols=["AAA"])
        self.assertEqual(len(self.reads), 1)
        self.assertTrue(_bits_equal(first, second))
        self.assertEqual(second["total_assets"].tolist(), [1.0, 2.0])

    def test_a_new_hub_revision_is_read_again(self):
        ds.load_dataset("Stocks-Quarterly-BalanceSheet", symbols=["AAA"])
        _fresh_process()
        self.sha[0] = "2" * 40
        second = ds.load_dataset("Stocks-Quarterly-BalanceSheet", symbols=["AAA"])
        self.assertEqual(len(self.reads), 2)
        self.assertEqual(second["total_assets"].tolist(), [1.0, 2.5])

    def test_minute_datasets_are_not_cached(self):
        self.assertTrue(ds._load_dataset_uncacheable({"path": "Stocks-1Min-Price"}))
        self.assertTrue(ds._load_dataset_uncacheable({"path": "paperswithbacktest/Options-Daily-Price"}))
        self.assertFalse(ds._load_dataset_uncacheable({"path": "Stocks-Daily-Price"}))
        with ds.superset_reads():
            self.assertTrue(ds._load_dataset_uncacheable({"path": "Stocks-Daily-Price"}))

    def test_a_local_pit_universe_turns_the_cache_off(self):
        with mock.patch.dict(os.environ, {"PWB_PIT_UNIVERSE_DIR": self.root}):
            ds.load_dataset("Stocks-Quarterly-BalanceSheet", symbols=["AAA"])
        self.assertEqual(self.entries(), [])


class CostScheduleTest(_CacheTest):
    """The cost tables: a run that cannot read them is never served a cached schedule."""

    def setUp(self):
        super().setUp()
        self.table_ok = [True]
        self.table_reads = []

        def read_table(repo_id):
            self.table_reads.append(repo_id)
            if not self.table_ok[0]:
                raise OSError("offline: list_repo_files failed")
            pc.note_revision("table", repo_id, "c" * 40)
            if repo_id == commission.COST_PARAMS_REPO:
                return pd.DataFrame({"symbol": ["AAA"], "year": [2020], "spread_bps": [10.0],
                                     "lambda_bps": [0.0]})
            return pd.DataFrame({"symbol": [], "year": [], "spread_bps": []})

        self._patches = [
            mock.patch.object(commission, "_read_cost_table", side_effect=read_table),
            mock.patch.object(commission, "_roll_for", return_value={}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        super().tearDown()

    def schedules(self):
        return commission.get_cost_schedules(["AAA"], start_date="2020-01-01", end_date="2021-12-31",
                                             measurable={"AAA"}, active_years={"AAA": {2020, 2021}})

    def test_healthy_runs_share_the_entry(self):
        first = self.schedules()
        _fresh_process()
        second = self.schedules()
        self.assertEqual(first, second)
        self.assertEqual(pc.stats["hits"], 1)
        self.assertEqual(first[1]["AAA"].source, "measured")

    def test_offline_run_falls_back_exactly_as_without_the_cache(self):
        self.schedules()  # a healthy entry exists
        _fresh_process()
        self.table_ok[0] = False
        out = io.StringIO()
        with redirect_stdout(out):
            degraded = self.schedules()
        self.assertEqual(pc.stats["hits"], 0)
        self.assertNotEqual(degraded[1]["AAA"].source, "measured")
        self.assertIn("falling back to Roll", out.getvalue())
        self.assertEqual(len(self.entries()), 1)  # and it was not stored
        # Without the cache, the same degraded process gives the same thing.
        _fresh_process()
        with mock.patch.dict(os.environ, {"PWB_CACHE": "0"}):
            uncached = commission.get_cost_schedules(
                ["AAA"], start_date="2020-01-01", end_date="2021-12-31",
                measurable={"AAA"}, active_years={"AAA": {2020, 2021}})
        self.assertEqual(degraded, uncached)

    def test_a_table_that_fails_only_at_the_check_is_a_miss(self):
        self.schedules()
        _fresh_process()
        self.table_ok[0] = False
        self.assertIsNone(pc._resolve("table", commission.COST_PARAMS_REPO))
        self.assertTrue(pc._DEGRADED)


_WRITER = textwrap.dedent("""
    import sys, numpy as np, pandas as pd
    from pwb_toolbox.datasets import prepared_cache as pc
    path, seed = sys.argv[1], int(sys.argv[2])
    df = pd.DataFrame(np.random.default_rng(0).normal(size=(200_000, 8)))
    for _ in range(15):
        pc._dump(path, df, {"format": pc.FORMAT, "writer": seed})
        value, header = pc._load(path)
        assert value.equals(df), "torn read"
    print("ok")
""")


class ConcurrentWriteTest(_CacheTest):
    def test_two_processes_writing_one_key_leave_a_whole_file(self):
        path = os.path.join(self.root, "data", "ab", "ab" + "0" * 62 + ".pwbc")
        procs = [subprocess.Popen([sys.executable, "-c", _WRITER, path, str(i)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for i in range(2)]
        outs = [p.communicate(timeout=300) for p in procs]
        for p, (out, err) in zip(procs, outs):
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(out.strip(), "ok")
        value, header = pc._load(path)
        self.assertEqual(value.shape, (200_000, 8))
        leftovers = [n for n in os.listdir(os.path.dirname(path)) if n.startswith(".tmp-")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
