"""``CrossSectionalQuantileSignal``: deciles of a ranking of the whole universe.

The expected signals are computed with pandas from the same panel; the
indicator must match them on every bar, in backtrader's default vectorised
mode (which the indicator turns off) as bar by bar, skip the names the
strategy says are not members, and score each name once per bar.
"""

import contextlib
import io
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from pwb_toolbox.backtesting import (
    BaseStrategy,
    CrossSectionalQuantileSignal,
    MonthlyLongShortQuantilePortfolio,
)
from pwb_toolbox.backtesting import backtest_engine as be

from _synthetic import offline, panel

NAMES = [f"S{i:02d}" for i in range(30)]
BARS = 90
LOOKBACK, SKIP = 30, 5
OUT = {"S03", "S17", "S29"}  # not members from bar OUT_FROM on
OUT_FROM = 50


def _prices():
    rng = np.random.default_rng(7)
    return panel({
        s: 100 * np.exp(np.cumsum(rng.normal(0.0005 * (i % 7 - 3), 0.02, BARS)))
        for i, s in enumerate(NAMES)
    })


def _expected(prices, exclude_from=None):
    """{bar: {name: +1/-1/0}} with pandas, for the bars the indicator can score."""
    close = prices.xs("close", axis=1, level=1)
    mom = close.shift(SKIP) / close.shift(LOOKBACK) - 1
    out = {}
    for i in range(LOOKBACK, BARS):
        row = mom.iloc[i]
        if exclude_from is not None and i >= exclude_from:
            row = row.drop(sorted(OUT))
        ranked = sorted(row.items(), key=lambda kv: (kv[1], kv[0]))
        n = len(ranked)
        signals = {s: 0 for s in NAMES}
        for k, (name, _) in enumerate(ranked):
            q = k * 10 // n
            signals[name] = 1 if q == 9 else -1 if q == 0 else 0
        out[i] = signals
    return out


class Recorder(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}), ("exclude_from", None))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.sig = {
            d._name: self.p.indicator_cls(d, universe=self.datas, **self.p.indicator_kwargs)
            for d in self.datas
        }
        self.seen = {}

    def is_member(self, data):
        name = data if isinstance(data, str) else data._name
        if self.p.exclude_from is not None and len(self) - 1 >= self.p.exclude_from and name in OUT:
            return False
        return super().is_member(data)

    def next(self):
        super().next()
        self.seen[len(self) - 1] = {name: int(line[0]) for name, line in self.sig.items()}


class Counter:
    """The default momentum, counting its calls."""

    def __init__(self):
        self.calls = 0

    def __call__(self, data):
        self.calls += 1
        return data.close[-SKIP] / data.close[-LOOKBACK] - 1


def _run(prices, strategy_cls=Recorder, cerebro_kwargs=None, short_borrow_bps=None, **kwargs):
    kw = {"lookback": LOOKBACK, "skip": SKIP, "quantiles": 10}
    kw.update(kwargs.pop("indicator_kwargs", {}))
    with offline(prices), contextlib.redirect_stdout(io.StringIO()):
        return be.run_strategy(
            indicator_cls=CrossSectionalQuantileSignal,
            indicator_kwargs=kw,
            strategy_cls=strategy_cls,
            strategy_kwargs=kwargs,
            symbols=NAMES,
            start_date="2020-01-01",
            cash=100_000.0,
            cerebro_kwargs=cerebro_kwargs,
            broker_kwargs={"commission": 0.0},
            short_borrow_bps=short_borrow_bps,
        )


class Deciles(unittest.TestCase):
    def setUp(self):
        self.prices = _prices()

    def _check(self, seen, expected):
        for i in range(BARS):
            if i < LOOKBACK:
                self.assertEqual(set(seen[i].values()), {0}, i)
            else:
                self.assertEqual(seen[i], expected[i], i)

    def test_top_decile_long_bottom_short_rest_flat(self):
        strategy = _run(self.prices)
        expected = _expected(self.prices)
        self._check(strategy.seen, expected)
        last = strategy.seen[BARS - 1]
        self.assertEqual(sum(v == 1 for v in last.values()), 3)
        self.assertEqual(sum(v == -1 for v in last.values()), 3)

    def test_same_bar_by_bar(self):
        vectorised = _run(self.prices)
        stepped = _run(self.prices, cerebro_kwargs={"runonce": False})
        self.assertEqual(vectorised.seen, stepped.seen)

    def test_non_members_are_skipped(self):
        strategy = _run(self.prices, exclude_from=OUT_FROM)
        expected = _expected(self.prices, exclude_from=OUT_FROM)
        self._check(strategy.seen, expected)
        for i in range(OUT_FROM, BARS):
            self.assertTrue(all(strategy.seen[i][s] == 0 for s in OUT), i)
        # and they were ranked before: one of them sat in a tail
        self.assertTrue(any(
            strategy.seen[i][s] != 0 for i in range(LOOKBACK, OUT_FROM) for s in OUT
        ))

    def test_ranked_once_per_bar(self):
        score = Counter()
        strategy = _run(self.prices, indicator_kwargs={"score": score})
        self._check(strategy.seen, _expected(self.prices))
        scored_bars = BARS - LOOKBACK
        self.assertEqual(score.calls, len(NAMES) * scored_bars)  # not 30 x 30 a bar
        (cache,) = strategy._pwb_xsq_cache.values()
        self.assertEqual(cache["rankings"], BARS)

    def test_custom_quantiles(self):
        strategy = _run(self.prices, indicator_kwargs={"quantiles": 5, "long_q": 0, "short_q": [4]})
        last = strategy.seen[BARS - 1]
        self.assertEqual(sum(v == 1 for v in last.values()), 6)
        self.assertEqual(sum(v == -1 for v in last.values()), 6)
        # reversed: the lowest quintile is long
        expected = _expected(self.prices)[BARS - 1]
        self.assertTrue(all(last[s] == 1 for s, v in expected.items() if v == -1))

    def test_too_few_names_is_flat(self):
        strategy = _run(self.prices, indicator_kwargs={"min_names": 31})
        self.assertTrue(all(set(v.values()) == {0} for v in strategy.seen.values()))

    def test_bad_parameters(self):
        for kwargs in ({"quantiles": 1}, {"skip": 30}, {"long_q": 10}, {"long_q": 0, "short_q": 0}):
            with self.assertRaises(ValueError):
                _run(self.prices, indicator_kwargs=kwargs)


class Template(unittest.TestCase):
    def test_monthly_long_short_with_borrow(self):
        prices = _prices()
        strategy = _run(
            prices, strategy_cls=MonthlyLongShortQuantilePortfolio, leverage=0.9,
            short_borrow_bps=50,
        )
        self.assertGreater(strategy.run_report["borrow"]["short_names"], 0)
        self.assertGreater(strategy.borrow_cost, 0.0)
        item = next(i for i in strategy.checks["items"] if i["id"] == "costs")
        self.assertEqual(item["detail"]["shortBorrowBps"], 50.0)
        self.assertEqual(strategy.funding_audit["margin"], 0)


if __name__ == "__main__":
    unittest.main()


class PointInTimeUniverse(unittest.TestCase):
    """With ``["sp500"]`` the owner's ``is_member`` comes from the harness."""

    def test_name_out_of_the_universe_is_not_ranked(self):
        import test_pit_hold_accounting as acc

        class Ranks(Recorder):
            pass

        case = type("Case", (acc._Base,), {"runTest": lambda self: None})()
        case.setUp()
        try:
            run = be.run_strategy

            def with_signal(*args, **kwargs):
                kwargs["indicator_cls"] = CrossSectionalQuantileSignal
                kwargs["indicator_kwargs"] = {
                    "lookback": 20, "skip": 0, "quantiles": 2, "min_names": 2,
                }
                return run(*args, **kwargs)

            with mock.patch.object(be, "run_strategy", with_signal), \
                    contextlib.redirect_stdout(io.StringIO()):
                strategy = case._run(Ranks)
        finally:
            case.tearDown()
        # the harness's own flags (its as-of tolerance moves the exit a few bars)
        out = strategy.pit_membership.out["X"]
        self.assertTrue(out.any())
        for i in range(30, len(out)):
            x = strategy.seen[i]["X"]
            if out[i]:
                self.assertEqual(x, 0, i)
                # A and B are still split between the two quantiles
                self.assertEqual(sorted((strategy.seen[i]["A"], strategy.seen[i]["B"])), [-1, 1], i)
            elif i >= 30 + int(np.flatnonzero(out)[-1]) + 1 or i < int(np.flatnonzero(out)[0]):
                self.assertIn(x, (1, -1), i)  # two names a quantile: always a tail
