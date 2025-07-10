from datetime import datetime
from tests.stubs import stub_environment

stub_environment()

from pwb_toolbox.performance import (
    hit_rate,
    average_win_loss,
    expectancy,
    profit_factor,
    trade_duration_distribution,
    turnover,
)


def sample_trades():
    return [
        {
            "entry": datetime(2020, 1, 1),
            "exit": datetime(2020, 1, 3),
            "direction": "long",
            "return": 0.05,
            "size": 1.0,
        },
        {
            "entry": datetime(2020, 1, 2),
            "exit": datetime(2020, 1, 4),
            "direction": "short",
            "return": -0.02,
            "size": -0.5,
        },
        {
            "entry": datetime(2020, 1, 5),
            "exit": datetime(2020, 1, 6),
            "direction": "long",
            "return": 0.01,
            "size": 1.0,
        },
    ]


def test_basic_trade_stats():
    trades = sample_trades()
    hr = hit_rate(trades)
    avg_win, avg_loss = average_win_loss(trades)
    exp = expectancy(trades)
    pf = profit_factor(trades)
    dists = trade_duration_distribution(trades)
    to = turnover(trades)

    assert round(hr, 6) == round(2 / 3, 6)
    assert round(avg_win, 6) == round(0.03, 6)
    assert round(avg_loss, 6) == round(-0.02, 6)
    assert round(exp, 6) == round(0.013333333333333332, 6)
    assert round(pf, 6) == round(3.0, 6)
    assert dists == {2: 2, 1: 1}
    assert round(to, 6) == round(3 / 5, 6)
