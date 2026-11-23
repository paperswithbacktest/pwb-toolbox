"""_resolve_reused_tickers in one pass gives what the per-ticker loop gave, exactly.

The loop of 0.1.54 is frozen below (``_old_resolve``, copied verbatim from
``origin/main`` on 23 Nov 2026) and is the oracle: random panels with reused
tickers, dated names, winners renamed or not, losers that empty a frame, names
absent from every frame, ``None`` and empty frames, several ``symbol`` and
``date`` dtypes, duplicate index labels, and groups that share a name (where
the loop's order matters and the new function must fall back to it). Frames,
dtypes, index, printed warnings and the returned dict are compared.
"""

import contextlib
import io
import random
import unittest

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as ds


def _old_resolve(frames: dict, reused: dict, start_date, end_date) -> dict:
    """Keep, for each reused bare ticker, the one instrument that covers the window.

    ``reused`` maps the bare ticker to the names loaded for it (itself, when the
    index has it, and its dated names). The winner's rows are renamed to the
    bare ticker; the other candidates' rows are dropped.
    """
    if not reused:
        return frames
    start = pd.Timestamp.min if start_date is None else pd.Timestamp(start_date)
    end = pd.Timestamp.max if end_date is None else pd.Timestamp(end_date)
    for bare, names in reused.items():
        spans = {}
        for frame in frames.values():
            if frame is None or frame.empty:
                continue
            sym = frame["symbol"].astype(str)
            for name in names:
                rows = frame.loc[sym == name, "date"]
                if rows.empty:
                    continue
                days = pd.to_datetime(rows)
                spans[name] = (int(((days >= start) & (days <= end)).sum()),
                               days.min(), days.max())
        if not spans:
            continue
        best = max(spans, key=lambda n: (spans[n][0], n == bare, n))
        losers = [n for n in spans if n != best]
        for repo, frame in list(frames.items()):
            if frame is None or frame.empty:
                continue
            sym = frame["symbol"].astype(str)
            frame = frame[~sym.isin(losers)].copy()
            if best != bare:
                sym = frame["symbol"].astype(str)
                frame["symbol"] = sym.where(sym != best, bare)
            frames[repo] = frame
        if best != bare or any(spans[n][0] for n in losers):
            def describe(n):
                count, first, last = spans[n]
                return f"'{n}' ({first:%Y-%m-%d}..{last:%Y-%m-%d}, {count} sessions in the window)"
            others = "; ".join(describe(n) for n in losers) or "none"
            loaded_as = f", loaded as '{bare}'" if best != bare else ""
            print(
                f"Warning: '{bare}' named several instruments over time; for this window it "
                f"resolves to {describe(best)}{loaded_as}. Other instruments under '{bare}': "
                f"{others}. Instruments are never stitched; name one explicitly to choose it."
            )
    return frames



def _bars(rng, symbol, n_max=40):
    start = pd.Timestamp("2000-01-03") + pd.Timedelta(days=int(rng.integers(0, 6000)))
    n = int(rng.integers(1, n_max))
    dates = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"symbol": symbol, "date": dates, "close": rng.random(n)})


def _case(seed):
    """``(frames, reused, start, end)``: a random panel in two or three repositories."""
    rng = np.random.default_rng(seed)
    py = random.Random(seed)
    n_bare = int(rng.integers(1, 12))
    reused, rows = {}, {}
    for b in range(n_bare):
        bare = f"T{b}"
        dated = [f"{bare}_{20000101 + int(rng.integers(0, 260000)):08d}" for _ in range(int(rng.integers(1, 4)))]
        dated = list(dict.fromkeys(dated))
        names = ([bare] if rng.random() < 0.7 else []) + dated
        if not names:
            names = dated
        reused[bare] = names
        for name in names + ([bare] if bare not in names and rng.random() < 0.3 else []):
            if rng.random() < 0.85:  # some names have no row at all
                rows[name] = _bars(rng, name)
    for k in range(int(rng.integers(0, 15))):  # names nobody asked to resolve
        rows[f"N{k}"] = _bars(rng, f"N{k}")
    if rng.random() < 0.25 and len(reused) >= 2:
        # Two groups sharing a name, or a group naming another's bare ticker.
        a, b = py.sample(list(reused), 2)
        reused[b] = reused[b] + ([a] if rng.random() < 0.5 else [reused[a][-1]])
    repos = ["Stocks-Daily-Price", "ETFs-Daily-Price", "Cryptocurrencies-Daily-Price"][: int(rng.integers(1, 4))]
    parts = {repo: [] for repo in repos}
    for name, frame in rows.items():
        for repo in repos:
            if rng.random() < (0.8 if repo == repos[0] else 0.25):  # a name may be in two repositories
                parts[repo].append(frame)
    frames = {}
    for repo in repos:
        if rng.random() < 0.1:
            frames[repo] = None
            continue
        frame = pd.concat(parts[repo], ignore_index=True) if parts[repo] else _bars(rng, "Z").iloc[:0]
        if len(frame) and rng.random() < 0.5:
            frame = frame.sample(frac=1.0, random_state=int(rng.integers(0, 1000)))  # rows out of order
        if len(frame) and rng.random() < 0.2:
            frame.index = rng.integers(0, 5, len(frame))  # duplicate labels
        kind = rng.integers(0, 4)
        if kind == 1:
            frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        elif kind == 2:
            frame["date"] = frame["date"].dt.date
        kind = rng.integers(0, 4)
        if kind == 1:
            frame["symbol"] = frame["symbol"].astype("category")
        elif kind == 2:
            frame["symbol"] = frame["symbol"].astype("string")
        elif kind == 3 and len(frame):
            frame = frame.copy()
            frame.iloc[0, frame.columns.get_loc("symbol")] = None  # a missing symbol
        frames[repo] = frame
    if rng.random() < 0.3:
        frames["Indices-Daily-Price"] = pd.DataFrame(columns=["symbol", "date", "close"])
    lo = pd.Timestamp("2000-01-03") + pd.Timedelta(days=int(rng.integers(0, 6000)))
    hi = lo + pd.Timedelta(days=int(rng.integers(0, 4000)))
    start = None if rng.random() < 0.15 else lo.date().isoformat()
    end = None if rng.random() < 0.15 else hi.date().isoformat()
    return frames, reused, start, end


def _copy(frames):
    return {k: (None if v is None else v.copy(deep=True)) for k, v in frames.items()}


def _run(fn, frames, reused, start, end):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(frames, reused, start, end)
    return result, out.getvalue()


class ResolveReusedPropertyTest(unittest.TestCase):
    def assertSameResult(self, got, ref):
        (frames_new, text_new), (frames_old, text_old) = got, ref
        self.assertEqual(text_new, text_old)
        self.assertEqual(list(frames_new), list(frames_old))
        for repo in frames_old:
            a, b = frames_new[repo], frames_old[repo]
            if b is None:
                self.assertIsNone(a)
                continue
            pd.testing.assert_frame_equal(a, b, check_exact=True, check_index_type=True,
                                          check_column_type=True, check_categorical=True)
            self.assertEqual(list(a.dtypes), list(b.dtypes))
            self.assertEqual(type(a.index), type(b.index))
            # Values, object for object (a "nan" string is not a NaN).
            self.assertEqual([repr(x) for x in a["symbol"].tolist()], [repr(x) for x in b["symbol"].tolist()])

    def _check(self, frames, reused, start, end):
        ref = _run(_old_resolve, _copy(frames), {k: list(v) for k, v in reused.items()}, start, end)
        got = _run(ds._resolve_reused_tickers, _copy(frames), {k: list(v) for k, v in reused.items()}, start, end)
        self.assertSameResult(got, ref)
        return ref

    def test_random_panels(self):
        printed = fallbacks = 0
        for seed in range(600):
            frames, reused, start, end = _case(seed)
            with self.subTest(seed=seed):
                _, text = self._check(frames, reused, start, end)
                printed += bool(text)
                fallbacks += not ds._reused_groups_disjoint(reused)
        # The generator does reach the interesting cases.
        self.assertGreater(printed, 300)
        self.assertGreater(fallbacks, 50)

    def test_the_returned_dict_is_the_argument(self):
        frames, reused, start, end = _case(3)
        arg = _copy(frames)
        self.assertIs(ds._resolve_reused_tickers(arg, reused, start, end), arg)

    def test_no_reused_ticker_returns_the_frames_untouched(self):
        frames, _, start, end = _case(5)
        arg = _copy(frames)
        before = {k: v for k, v in arg.items()}
        out = ds._resolve_reused_tickers(arg, {}, start, end)
        self.assertTrue(all(out[k] is before[k] for k in before))

    def test_names_without_rows_leave_the_frames_untouched_as_the_loop_did(self):
        frames, _, start, end = _case(7)
        self._check(frames, {"ABSENT": ["ABSENT", "ABSENT_20200101"]}, start, end)

    def test_a_loser_that_empties_a_frame_before_a_rename(self):
        """The loop stops touching a frame it has emptied: its ``symbol`` keeps its dtype."""
        rng = np.random.default_rng(0)
        only_loser = _bars(rng, "A_20050101")
        only_loser["symbol"] = only_loser["symbol"].astype("category")
        frames = {
            "ETFs-Daily-Price": only_loser,
            "Stocks-Daily-Price": pd.concat([_bars(rng, "A"), _bars(rng, "B_20060101", 200), _bars(rng, "B", 5)],
                                            ignore_index=True),
        }
        frames["Stocks-Daily-Price"]["date"] = pd.Timestamp("2010-01-04")  # A wins its group
        reused = {"A": ["A", "A_20050101"], "B": ["B", "B_20060101"]}
        self._check(frames, reused, "2000-01-01", "2030-01-01")
        # And when the rename comes first, the emptied frame was converted before it emptied.
        self._check(frames, {"B": ["B", "B_20060101"], "A": ["A", "A_20050101"]}, "2000-01-01", "2030-01-01")

    def test_a_frame_emptied_over_two_groups_with_a_rename_between(self):
        """Losers of the first and third groups fill a frame; the second renames its
        winner. The loop converted that frame's ``symbol`` at the second step, before
        the third emptied it."""
        rng = np.random.default_rng(1)
        losers = pd.concat([_bars(rng, "A_20050101"), _bars(rng, "C_20070101")], ignore_index=True)
        losers["symbol"] = losers["symbol"].astype("category")
        main = pd.concat([_bars(rng, "A"), _bars(rng, "B_20060101"), _bars(rng, "C")], ignore_index=True)
        main["date"] = pd.Timestamp("2010-01-04")
        frames = {"ETFs-Daily-Price": losers, "Stocks-Daily-Price": main}
        reused = {"A": ["A", "A_20050101"], "B": ["B_20060101"], "C": ["C", "C_20070101"]}
        self._check(frames, reused, "2000-01-01", "2030-01-01")
        self._check(frames, {"A": reused["A"], "C": reused["C"], "B": reused["B"]}, "2000-01-01", "2030-01-01")

    def test_the_warning_lists_the_other_instruments_in_the_loops_order(self):
        rng = np.random.default_rng(2)
        frames = {"Stocks-Daily-Price": pd.concat([_bars(rng, "Z_20030101"), _bars(rng, "Z_20010101"),
                                                   _bars(rng, "Z", 80)], ignore_index=True),
                  "ETFs-Daily-Price": _bars(rng, "Z_20020101")}
        for names in (["Z", "Z_20010101", "Z_20020101", "Z_20030101"],
                      ["Z_20030101", "Z", "Z_20020101", "Z_20010101"]):
            with self.subTest(names=names):
                _, text = self._check(frames, {"Z": names}, None, None)
                self.assertIn("Other instruments", text)

    def test_the_measured_cases_fb_and_aso(self):
        from test_reused_tickers import ACADEMY, AMSOUTH, BUFFER_ETF, CARBON_FUND, FACEBOOK

        frames = {"Stocks-Daily-Price": pd.concat([FACEBOOK, AMSOUTH, ACADEMY], ignore_index=True),
                  "ETFs-Daily-Price": pd.concat([BUFFER_ETF, CARBON_FUND], ignore_index=True)}
        reused = {"FB": ["FB", "FB_20220609"], "ASO": ["ASO", "ASO_20061103", "ASO_20090803"]}
        for start, end in (("2015-01-01", "2016-01-01"), ("2004-01-01", "2005-01-01"),
                           ("2021-01-01", "2026-01-01"), (None, None), ("1990-01-01", "1991-01-01")):
            with self.subTest(window=(start, end)):
                self._check(frames, reused, start, end)


if __name__ == "__main__":
    unittest.main()
