from datetime import datetime
from tests.stubs import stub_environment

stub_environment()

from pwb_toolbox.performance import (
    trade_implementation_shortfall,
    cumulative_implementation_shortfall,
    slippage_stats,
    latency_stats,
)


def sample_trades():
    return [
        {
            "signal_time": datetime(2020, 1, 1, 8, 59),
            "entry": datetime(2020, 1, 1, 9, 0),
            "exit": datetime(2020, 1, 1, 15, 0),
            "direction": "long",
            "return": 0.05,
            "model_return": 0.06,
            "entry_price": 101,
            "model_entry_price": 100,
            "exit_price": 105,
            "model_exit_price": 106,
        },
        {
            "signal_time": datetime(2020, 1, 2, 9, 5),
            "entry": datetime(2020, 1, 2, 9, 6),
            "exit": datetime(2020, 1, 2, 16, 0),
            "direction": "short",
            "return": 0.03,
            "model_return": 0.04,
            "entry_price": 49,
            "model_entry_price": 50,
            "exit_price": 48,
            "model_exit_price": 47,
        },
        {
            "signal_time": datetime(2020, 1, 3, 9, 10),
            "entry": datetime(2020, 1, 3, 9, 12),
            "exit": datetime(2020, 1, 3, 15, 0),
            "direction": "long",
            "return": 0.015,
            "model_return": 0.02,
            "entry_price": 50,
            "model_entry_price": 50,
            "exit_price": 51,
            "model_exit_price": 52,
        },
    ]


def test_live_vs_backtest_metrics():
    trades = sample_trades()

    shorts = [trade_implementation_shortfall(t) for t in trades]
    cum_short = cumulative_implementation_shortfall(trades)
    slip = slippage_stats(trades)
    latency = latency_stats(trades)

    assert round(shorts[0], 6) == round(0.01, 6)
    assert round(shorts[1], 6) == round(0.01, 6)
    assert round(shorts[2], 6) == round(0.005, 6)
    assert round(cum_short, 6) == round(0.025, 6)
    assert round(slip["avg_entry_slippage"], 6) == round(0.01, 6)
    assert round(slip["avg_exit_slippage"], 6) == round(0.01664710907986701, 6)
    assert round(latency["avg_latency_sec"], 6) == round(80.0, 6)
    assert latency["max_latency_sec"] == 120.0
