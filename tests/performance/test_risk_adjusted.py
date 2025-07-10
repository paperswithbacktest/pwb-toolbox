from tests.stubs import pd, stub_environment

stub_environment()

from pwb_toolbox.performance import (
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    omega_ratio,
    information_ratio,
)


def sample_prices():
    idx = pd.date_range("2020-01-01", periods=6)
    prices = pd.Series([100, 110, 105, 115, 90, 95])
    prices.index = idx
    return prices


def benchmark_prices():
    idx = pd.date_range("2020-01-01", periods=6)
    prices = pd.Series([100, 108, 107, 110, 100, 103])
    prices.index = idx
    return prices


def test_risk_adjusted_metrics():
    prices = sample_prices()
    bench = benchmark_prices()
    sr = sharpe_ratio(prices)
    so = sortino_ratio(prices)
    cal = calmar_ratio(prices)
    om = omega_ratio(prices)
    ir = information_ratio(prices, bench)
    assert round(sr, 6) == round(-0.3200899679814901, 6)
    assert round(so, 6) == round(-0.3852543912741862, 6)
    assert round(cal, 6) == round(-4.253241162564978, 6)
    assert round(om, 6) == round(0.9541472729442665, 6)
    assert round(ir, 6) == round(-2.3691120809817683, 6)
