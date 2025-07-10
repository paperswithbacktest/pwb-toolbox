from tests.stubs import pd, stub_environment

stub_environment()

from pwb_toolbox.performance import (
    annualized_volatility,
    max_drawdown,
    ulcer_index,
    ulcer_performance_index,
    parametric_var,
    parametric_expected_shortfall,
    tail_ratio,
)


def sample_prices():
    idx = pd.date_range("2020-01-01", periods=6)
    prices = pd.Series([100, 110, 105, 115, 90, 95])
    prices.index = idx
    return prices


def test_annualized_volatility():
    prices = sample_prices()
    vol = annualized_volatility(prices)
    assert round(vol, 6) == round(1.8976878090557243, 6)


def test_max_drawdown():
    prices = sample_prices()
    depth, duration = max_drawdown(prices)
    assert round(depth, 6) == round(-0.21739130434782605, 6)
    assert duration == 2


def test_ulcer_metrics():
    prices = sample_prices()
    ui = ulcer_index(prices)
    upi = ulcer_performance_index(prices)
    assert round(ui, 6) == round(0.11515991895360117, 6)
    assert round(upi, 6) == round(-8.028988318482583, 6)


def test_parametric_var_es_tail_ratio():
    prices = sample_prices()
    var = parametric_var(prices)
    es = parametric_expected_shortfall(prices)
    ratio = tail_ratio(prices)
    assert round(var, 6) == round(0.1990413339257849, 6)
    assert round(es, 6) == round(0.24899351383065385, 6)
    assert round(ratio, 6) == round(0.43809523809523865, 6)
