from tests.stubs import pd, stub_environment
import types

stub_environment()

from pwb_toolbox.backtest.execution_models import (
    ImmediateExecutionModel,
    StandardDeviationExecutionModel,
    VolumeWeightedAveragePriceExecutionModel,
    VolumePercentageExecutionModel,
    TimeProfileExecutionModel,
    TrailingLimitExecutionModel,
    AdaptiveExecutionModel,
    BufferedExecutionModel,
)

import backtrader as bt  # type: ignore


def make_strategy(prices, symbols):
    strat = bt.Strategy()
    strat.prices = prices
    strat.datas = [types.SimpleNamespace(_name=s) for s in symbols]
    return strat


def test_immediate_execution():
    prices = pd.DataFrame({"AAPL": [1, 2]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = ImmediateExecutionModel()
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [("target", "AAPL", 1.0)]


def test_standard_deviation_execution():
    prices = pd.DataFrame({"AAPL": [1.0, 2.0, 3.5, 2.0]}, index=[0, 1, 2, 3])
    strat = make_strategy(prices, ["AAPL"])
    model = StandardDeviationExecutionModel(lookback=3, threshold=0.1)
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [("target", "AAPL", 1.0)]


def test_vwap_execution_steps():
    prices = pd.DataFrame({"AAPL": [1, 2]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = VolumeWeightedAveragePriceExecutionModel(steps=2)
    model.execute(strat, {"AAPL": 1.0})
    model.execute(strat, {"AAPL": 1.0})
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [
        ("target", "AAPL", 0.5),
        ("target", "AAPL", 1.0),
    ]


def test_volume_percentage_execution():
    prices = pd.DataFrame({"AAPL": [1, 2]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = VolumePercentageExecutionModel(percentage=0.5)
    model.execute(strat, {"AAPL": 1.0})
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [
        ("target", "AAPL", 0.5),
        ("target", "AAPL", 0.75),
    ]


def test_time_profile_execution():
    prices = pd.DataFrame({"AAPL": [1, 2]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = TimeProfileExecutionModel(profile={0: 0.5, 1: 0.5})
    model.execute(strat, {"AAPL": 1.0})
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [
        ("target", "AAPL", 0.5),
        ("target", "AAPL", 0.5),
    ]


def test_trailing_limit_execution():
    prices = pd.DataFrame({"AAPL": [100, 101]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = TrailingLimitExecutionModel(trail=0.01)
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [("buy", "AAPL", "limit", 101 * (1 - 0.01))]


def test_adaptive_execution():
    prices = pd.DataFrame({"AAPL": [1.0, 1.05]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = AdaptiveExecutionModel(threshold=0.02, steps=2)
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [("target", "AAPL", 1.0)]

    strat.orders.clear()
    prices = pd.DataFrame({"AAPL": [1.0, 1.01]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = AdaptiveExecutionModel(threshold=0.02, steps=2)
    model.execute(strat, {"AAPL": 1.0})
    assert strat.orders == [("target", "AAPL", 0.5)]


def test_buffered_execution():
    prices = pd.DataFrame({"AAPL": [1, 2]}, index=[0, 1])
    strat = make_strategy(prices, ["AAPL"])
    model = BufferedExecutionModel(buffer=0.05)
    model.execute(strat, {"AAPL": 1.0})
    model.execute(strat, {"AAPL": 1.02})
    model.execute(strat, {"AAPL": 0.0})
    assert strat.orders == [
        ("target", "AAPL", 1.0),
        ("target", "AAPL", 0.0),
    ]

