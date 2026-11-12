"""The array-backed feed must give the same backtest as backtrader's PandasData,
and must be the feed ``run_strategy`` actually builds on backtrader.

0.1.42 to 0.1.49 shipped the class switched off: the engine test read an
instance attribute off the class, so ``ArrayPandasData`` was
``bt.feeds.PandasData`` and every backtest ran on the slow feed. The two
``RunStrategyFeedTest`` cases fail on that code.
"""

import unittest

import numpy as np
import pandas as pd

from pwb_toolbox import engine
from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.backtesting.feeds import ArrayPandasData

from _synthetic import offline, panel

bt = engine.load()


def _frames(n_sym=12, n_bars=600, seed=1):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2010-01-04", periods=n_bars)
    out = {}
    for i in range(n_sym):
        close = 50 * np.exp(np.cumsum(rng.normal(0, 0.012, n_bars)))
        out[f"S{i}"] = pd.DataFrame(
            {"open": close * 0.998, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e5},
            index=index,
        )
    return out


class MonthlyEqualWeight(bt.Strategy):
    def __init__(self):
        self.values = []
        self.last = None

    def next(self):
        self.values.append(self.broker.getvalue())
        today = self.datas[0].datetime.date(0)
        if (today.year, today.month) != self.last:
            self.last = (today.year, today.month)
            for data in self.datas:
                self.order_target_percent(data, target=0.95 / len(self.datas))


def _run(feed_cls, frames, **cerebro_kwargs):
    cerebro = bt.Cerebro(**cerebro_kwargs)
    for name, frame in frames.items():
        cerebro.adddata(feed_cls(dataname=frame), name=name)
    cerebro.addstrategy(MonthlyEqualWeight)
    cerebro.broker.set_cash(1_000_000)
    cerebro.broker.setcommission(commission=0.0005)
    return cerebro.run()[0]


@unittest.skipUnless(engine.is_backtrader(), "the array feed only exists on backtrader")
class ArrayFeedTest(unittest.TestCase):
    def test_same_nav_path_as_pandas_data(self):
        frames = _frames()
        reference = _run(bt.feeds.PandasData, frames)
        fast = _run(ArrayPandasData, frames)
        self.assertEqual(len(reference.values), len(fast.values))
        np.testing.assert_allclose(reference.values, fast.values, rtol=0, atol=1e-9)

    def test_same_dates_and_bar_values(self):
        frames = _frames(n_sym=2, n_bars=50)
        reference = _run(bt.feeds.PandasData, frames)
        fast = _run(ArrayPandasData, frames)
        for ref_data, fast_data in zip(reference.datas, fast.datas):
            self.assertEqual(len(ref_data), len(fast_data))
            self.assertEqual(ref_data.datetime.date(0), fast_data.datetime.date(0))
            self.assertEqual(ref_data.close[0], fast_data.close[0])
            self.assertEqual(ref_data.open[-10], fast_data.open[-10])

    def test_stdstats_off_does_not_change_the_nav(self):
        frames = _frames(n_sym=4, n_bars=300)
        with_observers = _run(ArrayPandasData, frames)
        without = _run(ArrayPandasData, frames, stdstats=False)
        np.testing.assert_allclose(with_observers.values, without.values, rtol=0, atol=1e-9)


class _RecordFeeds(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        self.feed_types = [type(data) for data in self.datas]

    def next(self):
        pass


@unittest.skipUnless(engine.is_backtrader(), "the array feed only exists on backtrader")
class RunStrategyFeedTest(unittest.TestCase):
    def test_array_feed_is_switched_on_under_backtrader(self):
        self.assertIsNot(ArrayPandasData, bt.feeds.PandasData)
        self.assertTrue(issubclass(ArrayPandasData, bt.feeds.PandasData))
        self.assertIsNot(ArrayPandasData._load, bt.feeds.PandasData._load)

    def test_run_strategy_builds_its_feeds_from_arrays(self):
        rng = np.random.default_rng(3)
        closes = {s: 50 * np.exp(np.cumsum(rng.normal(0, 0.01, 60))) for s in ("A", "B")}
        with offline(panel(closes)):
            strategy = be.run_strategy(
                indicator_cls=None,
                indicator_kwargs={},
                strategy_cls=_RecordFeeds,
                strategy_kwargs={},
                symbols=["A", "B"],
                start_date="2020-01-01",
                cash=100_000.0,
                broker_kwargs={"commission": 0.0},
            )
        self.assertEqual(len(strategy.feed_types), 2)
        for feed_type in strategy.feed_types:
            self.assertTrue(issubclass(feed_type, ArrayPandasData))
            self.assertIs(feed_type._load, ArrayPandasData._load)
            self.assertIsNot(feed_type._load, bt.feeds.PandasData._load)


if __name__ == "__main__":
    unittest.main()
