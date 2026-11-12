"""The 0.1.50 speed-ups of the data path change no number.

* the in-process memo of shard reads serves the frame a fresh read gives, never
  the stored object, and is keyed by the file on disk and the filters;
* ``get_pricing`` reads only the monthly shards of its window and returns the
  panel it returned when it read them all;
* the Roll fallback of the cost schedules reuses the shards ``run_strategy``
  just read, with the estimate unchanged;
* ``_era_cuts`` (one pass) and ``FillAudit`` (one date per bar) match their
  per-column, per-feed definitions.

Fake repositories are parquet files in a temporary directory, served through
mocks of the Hub snapshot and ``hf_hub_download``: nothing touches the network.
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import pwb_toolbox.datasets as ds
from pwb_toolbox import engine
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.backtesting import commission

bt = engine.load()

STK = "paperswithbacktest/Stocks-Daily-Price"
ETF = "paperswithbacktest/ETFs-Daily-Price"
MONTHS = [f"2019-{m:02d}" for m in range(1, 13)] + [f"2020-{m:02d}" for m in range(1, 13)]


def _daily(symbols, start="2019-01-01", end="2020-12-31", seed=0, holes=(), bounce=0.0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    rows = []
    for i, symbol in enumerate(symbols):
        close = 20 * (i + 1) * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
        # a bid-ask bounce, so that Roll has a spread to find
        close = close * (1 + bounce * rng.choice([-1.0, 1.0], len(days)))
        frame = pd.DataFrame({
            "symbol": symbol,
            "date": days.strftime("%Y-%m-%d"),
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": rng.integers(1, 10_000, len(days)),
            "adj_close": close,
        })
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True)
    for symbol, lo, hi in holes:  # (symbol, first missing day, last missing day)
        out = out[~((out["symbol"] == symbol) & (out["date"] >= lo) & (out["date"] <= hi))]
    return out.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def _write(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)


class _Hub:
    """Several fake dataset repositories on disk, and the mocks that serve them."""

    def __init__(self, root, tables):
        self.root = root
        self.files = {}
        self.downloaded = []
        for name, table in tables.items():
            if isinstance(table, dict):  # {file name: frame}
                parts = table
            else:
                parts = {"data/train-00000-of-00001.parquet": table}
            self.files[name] = []
            for fname, frame in parts.items():
                _write(frame, os.path.join(root, name, fname))
                self.files[name].append(fname)

    @staticmethod
    def monthly(df):
        return {f"data/train-{m}.parquet": df[df["date"].str.startswith(m)] for m in MONTHS
                if df["date"].str.startswith(m).any()}

    def snapshot(self, repo_id, token):
        return ("sha", sorted(self.files[repo_id.split("/")[1]]))

    def download(self, **kw):
        name = kw["repo_id"].split("/")[1]
        self.downloaded.append((name, kw["filename"]))
        return os.path.join(self.root, name, kw["filename"])

    @contextlib.contextmanager
    def serving(self):
        with mock.patch.dict(os.environ, {"HF_ACCESS_TOKEN": "x"}), \
             mock.patch.object(ds, "_get_pwb_api_key", return_value=None), \
             mock.patch.object(ds, "_hub_snapshot", side_effect=self.snapshot), \
             mock.patch.object(ds, "hf_hub_download", side_effect=self.download), \
             contextlib.redirect_stdout(io.StringIO()):
            yield


class _Counting:
    """Counts the real shard reads under the memo."""

    def __init__(self):
        self.calls = 0
        self.real = ds._read_one_parquet

    def __call__(self, *a, **k):
        self.calls += 1
        return self.real(*a, **k)


class _MemoCase(unittest.TestCase):
    def setUp(self):
        ds._READ_MEMO.clear()
        self.tmp = tempfile.mkdtemp()
        self.reads = _Counting()
        self.patch = mock.patch.object(ds, "_read_one_parquet", side_effect=self.reads)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        ds._READ_MEMO.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)


class ReadMemoTest(_MemoCase):
    def setUp(self):
        super().setUp()
        self.prices = _daily(["AAA", "BBB", "CCC", "DDD"])
        self.hub = _Hub(self.tmp, {"Some-Daily-Table": _Hub.monthly(self.prices)})

    def _load(self, **kw):
        with self.hub.serving():
            return ds.load_dataset("Some-Daily-Table", **kw)

    def test_a_second_identical_load_reads_nothing_and_returns_the_same_frame(self):
        first = self._load(symbols=["AAA", "CCC"])
        n = self.reads.calls
        self.assertEqual(n, 24)
        second = self._load(symbols=["CCC", "AAA"])  # same set, other order
        self.assertEqual(self.reads.calls, n)
        pd.testing.assert_frame_equal(first, second)

    def test_the_caller_never_holds_the_stored_frame(self):
        first = self._load(symbols=["AAA"])
        first.loc[:, "close"] = -1.0
        first["extra"] = 1
        second = self._load(symbols=["AAA"])
        self.assertTrue((second["close"] > 0).all())
        self.assertNotIn("extra", second.columns)

    def test_a_single_shard_dataset_is_copied_too(self):
        hub = _Hub(self.tmp, {"One-File": _daily(["AAA"], end="2019-02-28")})
        with hub.serving():
            first = ds.load_dataset("One-File")
            first["close"] = 0.0
            second = ds.load_dataset("One-File")
        self.assertTrue((second["close"] > 0).all())
        self.assertEqual(self.reads.calls, 1)

    def test_same_frame_as_without_the_memo(self):
        with mock.patch.dict(os.environ, {"PWB_READ_MEMO_MB": "0"}):
            reference = self._load(symbols=["BBB", "DDD"], start="2019-03-05", end="2020-02-10")
        self.assertEqual(len(ds._READ_MEMO._entries), 0)
        cold = self._load(symbols=["BBB", "DDD"], start="2019-03-05", end="2020-02-10")
        warm = self._load(symbols=["BBB", "DDD"], start="2019-03-05", end="2020-02-10")
        pd.testing.assert_frame_equal(reference, cold)
        pd.testing.assert_frame_equal(reference, warm)

    def test_other_filters_are_other_reads(self):
        self._load(symbols=["AAA"])
        n = self.reads.calls
        self._load(symbols=["AAA", "BBB"])
        self.assertEqual(self.reads.calls, 2 * n)
        self._load(symbols=["AAA"], columns=["close"])
        self.assertEqual(self.reads.calls, 3 * n)

    def test_a_rewritten_file_is_read_again(self):
        self._load(symbols=["AAA"])
        n = self.reads.calls
        path = os.path.join(self.tmp, "Some-Daily-Table", "data/train-2020-12.parquet")
        changed = self.prices[self.prices["date"].str.startswith("2020-12")].copy()
        changed["close"] *= 2
        _write(changed, path)
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
        out = self._load(symbols=["AAA"])
        self.assertEqual(self.reads.calls, n + 1)
        dec = out[out["date"].astype(str).str.startswith("2020-12")]
        ref = changed[changed["symbol"] == "AAA"]
        np.testing.assert_allclose(dec["close"].to_numpy(), ref["close"].to_numpy())

    def test_switched_off_with_a_zero_budget(self):
        with mock.patch.dict(os.environ, {"PWB_READ_MEMO_MB": "0"}):
            self._load(symbols=["AAA"])
            self._load(symbols=["AAA"])
        self.assertEqual(self.reads.calls, 48)

    def test_a_read_larger_than_the_budget_keeps_what_it_stored(self):
        piece = ds._read_one_parquet(
            os.path.join(self.tmp, "Some-Daily-Table", "data/train-2019-01.parquet"), ["AAA"]
        )
        self.reads.calls = 0
        budget_mb = 5.5 * ds._frame_bytes(piece) / (1024 * 1024)
        with mock.patch.dict(os.environ, {"PWB_READ_MEMO_MB": str(budget_mb)}):
            self._load(symbols=["AAA"])
            self.assertEqual(len(ds._READ_MEMO._entries), 5)
            self._load(symbols=["AAA"])
        # the five first months stay stored and are served; the other 19 are read
        self.assertEqual(self.reads.calls, 24 + 19)
        self.assertLessEqual(ds._READ_MEMO.nbytes, budget_mb * 1024 * 1024)

    def test_superset_reads_are_off_by_default_and_exact_when_on(self):
        with mock.patch.dict(os.environ, {"PWB_READ_MEMO_MB": "0"}):
            reference = self._load(symbols=["BBB"])
        self._load(symbols=["AAA", "BBB", "CCC"])
        n = self.reads.calls
        self._load(symbols=["BBB"])
        self.assertEqual(self.reads.calls, n + 24)  # off by default: read again
        ds._READ_MEMO.clear()
        self._load(symbols=["AAA", "BBB", "CCC"])
        n = self.reads.calls
        with ds.superset_reads():
            served = self._load(symbols=["BBB"])
        self.assertEqual(self.reads.calls, n)
        pd.testing.assert_frame_equal(reference, served)


# --------------------------------------------------------------------------- #
# get_pricing: only the shards of the window                                  #
# --------------------------------------------------------------------------- #
def _universe(rows):
    return pd.DataFrame({"symbol": [r[0] for r in rows], "repo_id": [r[1] for r in rows],
                         "liquidity": 1.0, "max_pct_change": 0.1})


class PricingShardsTest(_MemoCase):
    def setUp(self):
        super().setUp()
        stocks = _daily(["AAA", "BBB", "OLD", "DUAL"], seed=1,
                        holes=[("OLD", "2019-06-01", "2020-12-31")])
        etfs = pd.concat([_daily(["SPY", "XLK"], seed=2), _daily(["DUAL"], seed=3)], ignore_index=True)
        self.tables = {
            "Stocks-Daily-Price": _Hub.monthly(stocks),
            "ETFs-Daily-Price": _Hub.monthly(etfs.sort_values(["date", "symbol"], kind="stable")),
            "Indices-Daily-Price": _daily(["SPX"], seed=4),
            "Forex-Daily-Price": _daily(["EURUSD"], seed=7),
            "Universe-Daily-Price": _universe([
                ("AAA", STK), ("BBB", STK), ("OLD", STK), ("DUAL", STK), ("DUAL", ETF),
                ("SPY", ETF), ("XLK", ETF), ("SPX", "paperswithbacktest/Indices-Daily-Price"),
            ]),
        }
        self.hub = _Hub(self.tmp, self.tables)

    def _pricing(self, symbols, prune=True, **kw):
        ds._READ_MEMO.clear()
        self.hub.downloaded.clear()
        patches = [] if prune else [mock.patch.object(ds, "_pricing_shard_window", return_value=None)]
        with self.hub.serving(), contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            out = ds.get_pricing(symbols, fields=["open", "high", "low", "close"], **kw)
        files = [f for name, f in self.hub.downloaded if name in ("Stocks-Daily-Price", "ETFs-Daily-Price")]
        return out, files

    def _same(self, symbols, **kw):
        ref, all_files = self._pricing(symbols, prune=False, **kw)
        out, files = self._pricing(symbols, **kw)
        pd.testing.assert_frame_equal(ref, out)
        self.assertEqual(dict(ref.attrs["pwb_routes"]), dict(out.attrs["pwb_routes"]))
        return all_files, files

    def test_stocks_read_only_the_months_of_the_window(self):
        all_files, files = self._same(["AAA", "BBB"], start_date="2020-03-01", end_date="2020-08-15")
        self.assertEqual(len(all_files), 24)
        # February is in the one-day slack before 1 March
        self.assertEqual(sorted(files), [f"data/train-2020-{m:02d}.parquet" for m in range(2, 9)])

    def test_open_end_and_default_dates(self):
        self._same(["AAA"], start_date="2019-11-20")
        all_files, files = self._same(["AAA"], start_date="2020-01-01", end_date=None)
        self.assertEqual(len(files), 13)  # December 2019 is in the one-day slack

    def test_a_name_with_no_row_in_the_window_disappears_as_before(self):
        self._same(["AAA", "OLD"], start_date="2020-01-01", end_date="2020-12-31")

    def test_nothing_in_the_window_comes_out_as_before(self):
        all_files, files = self._same(["OLD"], start_date="2020-01-01", end_date="2020-12-31")
        self.assertEqual(len(files), 13 + 24)  # the window, then everything again

    def test_a_contested_ticker_reads_every_shard(self):
        all_files, files = self._same(["DUAL", "AAA"], start_date="2020-06-01", end_date="2020-07-31")
        self.assertEqual(len(files), len(all_files))

    def test_etfs_with_a_proxy_and_extend_read_every_shard(self):
        all_files, files = self._same(["SPY"], start_date="2020-06-01", end_date="2020-07-31", extend=True)
        self.assertEqual(len(files), len(all_files))
        all_files, files = self._same(["XLK"], start_date="2020-06-01", end_date="2020-07-31", extend=True)
        self.assertLess(len(files), len(all_files))
        all_files, files = self._same(["SPY"], start_date="2020-06-01", end_date="2020-07-31")
        self.assertLess(len(files), len(all_files))

    def test_mixed_repositories(self):
        self._same(["AAA", "XLK", "SPX"], start_date="2019-07-01", end_date="2020-02-29")

    def test_a_strategy_reload_after_get_pricing_reuses_the_window_shards(self):
        with self.hub.serving():
            ds.get_pricing(["AAA", "BBB"], start_date="2020-03-01", end_date="2020-08-15")
            n = self.reads.calls
            ds.load_dataset("Stocks-Daily-Price", symbols=["AAA", "BBB"])
        # the 7 shards of the window were stored, the 17 others are read now
        self.assertEqual(self.reads.calls - n, 17)

    def test_nested_loads_read_every_shard(self):
        seen = []
        real = ds._shards_in_window

        def spy(names, window, dataset_name):
            seen.append((dataset_name, window))
            return real(names, window, dataset_name)

        with mock.patch.object(ds, "_shards_in_window", side_effect=spy):
            self._pricing(["AAA", "SPX"], start_date="2020-03-01", end_date="2020-08-15")
        windows = dict(seen)
        self.assertIsNotNone(windows["Stocks-Daily-Price"])
        self.assertIsNone(windows["Indices-Daily-Price"])
        self.assertIsNone(windows["Universe-Daily-Price"])


class RollFallbackTest(_MemoCase):
    def setUp(self):
        super().setUp()
        stocks = _daily(["AAA", "BBB", "CCC", "ZZZ_20190901"], seed=5, bounce=0.01)
        self.hub = _Hub(self.tmp, {
            "Stocks-Daily-Price": _Hub.monthly(stocks),
            "ETFs-Daily-Price": _Hub.monthly(_daily(["SPY"], seed=6)),
            "Universe-Daily-Price": _universe([("AAA", STK), ("BBB", STK), ("CCC", STK),
                                               ("ZZZ_20190901", STK), ("SPY", ETF)]),
        })

    def test_roll_reuses_the_panel_shards_with_the_same_estimate(self):
        with self.hub.serving(), mock.patch.dict(os.environ, {"PWB_READ_MEMO_MB": "0"}):
            reference = commission._roll_for(["BBB", "ZZZ_20190901"], "2019-04-01")
        self.assertEqual(set(reference), {"BBB", "ZZZ_20190901"})
        with self.hub.serving():
            ds.get_pricing(["AAA", "BBB", "CCC", "ZZZ_20190901"], fields=["open", "high", "low", "close"],
                           start_date="2019-04-01", extend=True)
            n = self.reads.calls
            served = commission._roll_for(["BBB", "ZZZ_20190901"], "2019-04-01")
        self.assertEqual(self.reads.calls, n)
        self.assertEqual(reference, served)


# --------------------------------------------------------------------------- #
# _era_cuts and FillAudit                                                     #
# --------------------------------------------------------------------------- #
class EraCutsTest(unittest.TestCase):
    def _panel(self, seed, n_days=3000, n_sym=300, index=None):
        rng = np.random.default_rng(seed)
        index = index if index is not None else pd.bdate_range("1995-01-02", periods=n_days)
        data = rng.normal(size=(len(index), n_sym))
        mask = np.ones_like(data, dtype=bool)
        for j in range(n_sym):
            kind = j % 6
            if kind == 1:  # one hole of 2-4 years
                a = rng.integers(0, len(index) // 2)
                mask[a:a + rng.integers(400, 1100), j] = False
            elif kind == 2:  # two holes
                mask[100:700, j] = False
                mask[1500:2300, j] = False
            elif kind == 3:  # late start, early end
                mask[: rng.integers(0, len(index)), j] = False
                mask[-rng.integers(1, 200):, j] = False
            elif kind == 4:  # a hole of exactly two years and one day, or one day short
                a = 300
                mask[a:a + 523 + (j % 2), j] = False
            elif kind == 5:  # almost empty
                mask[:, j] = False
                mask[rng.integers(0, len(index)), j] = True
        return pd.DataFrame(np.where(mask, data, np.nan), index=index,
                            columns=[f"S{j}" for j in range(n_sym)])

    def test_matches_the_per_column_definition(self):
        for seed in range(4):
            closes = self._panel(seed)
            for gap in (1, 2, 3):
                expected = be._era_cuts_by_column(closes, gap)
                self.assertEqual(be._era_cuts(closes, gap), expected)
                self.assertTrue(expected)

    def test_exact_threshold_on_calendar_days(self):
        index = pd.DatetimeIndex(["2000-01-03", "2002-01-03", "2002-01-04", "2004-01-05", "2010-01-04"])
        closes = pd.DataFrame({"A": [1.0, np.nan, 1.0, 1.0, np.nan], "B": [1.0, 1.0, np.nan, np.nan, 1.0]},
                              index=index)
        for gap in (1, 2, 5):
            self.assertEqual(be._era_cuts(closes, gap), be._era_cuts_by_column(closes, gap))

    def test_other_index_resolutions_and_zones(self):
        closes = self._panel(9, n_days=2000, n_sym=40)
        for index in (closes.index.as_unit("s"), closes.index.tz_localize("America/New_York")):
            other = closes.set_axis(index, axis=0)
            self.assertEqual(be._era_cuts(other, 2), be._era_cuts_by_column(other, 2))

    def test_empty_panels(self):
        self.assertEqual(be._era_cuts(pd.DataFrame(index=pd.DatetimeIndex([])), 2), {})
        self.assertEqual(be._era_cuts(pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex(["2020-01-01"])), 2), {})


class _PerFeedFillAudit(bt.Analyzer):
    """``FillAudit.next`` of 0.1.49: one date conversion per feed and bar."""

    params = (("inactive", None),)

    def start(self):
        self.held = {}

    def next(self):
        inactive = self.p.inactive or {}
        for data in self.datas:
            years = inactive.get(data._name)
            if not years:
                continue
            year = data.datetime.date(0).year
            if year not in years:
                continue
            if self.strategy.getposition(data).size:
                entry = self.held.setdefault(data._name, {"bars": 0, "years": set()})
                entry["bars"] += 1
                entry["years"].add(year)

    def get_analysis(self):
        return be.FillAudit.get_analysis(self)


class _Hold(bt.Strategy):
    def next(self):
        if len(self) == 3:
            for i, data in enumerate(self.datas):
                if i % 2 == 0:
                    self.order_target_percent(data, 0.1)


class FillAuditTest(unittest.TestCase):
    def test_same_analysis_with_one_conversion_per_bar(self):
        index = pd.bdate_range("2017-01-02", "2020-12-31")
        cerebro = bt.Cerebro(stdstats=False)
        rng = np.random.default_rng(0)
        names = [f"S{i}" for i in range(12)]
        for name in names:
            close = 30 * np.exp(np.cumsum(rng.normal(0, 0.01, len(index))))
            frame = pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=index)
            cerebro.adddata(bt.feeds.PandasData(dataname=frame), name=name)
        inactive = {name: {2018, 2020} if i % 3 else {2019} for i, name in enumerate(names)}
        cerebro.addstrategy(_Hold)
        cerebro.addanalyzer(be.FillAudit, _name="new", inactive=inactive)
        cerebro.addanalyzer(_PerFeedFillAudit, _name="old", inactive=inactive)
        cerebro.broker.set_cash(1e6)
        strategy = cerebro.run()[0]
        new = strategy.analyzers.new.get_analysis()
        old = strategy.analyzers.old.get_analysis()
        self.assertEqual(new, old)
        self.assertTrue(new)
        self.assertLessEqual(len(strategy.analyzers.new._years_of), len(index))


if __name__ == "__main__":
    unittest.main()
