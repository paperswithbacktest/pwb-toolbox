from tests.stubs import pd, stub_environment

stub_environment()

from pwb_toolbox.performance import (
    total_return,
    cagr,
    returns_table,
    rolling_cumulative_return,
)


def sample_prices(start="2020-01-01", periods=366):
    idx = pd.date_range(start, periods=periods)
    prices = pd.Series([100 + i for i in range(periods)])
    prices.index = idx
    return prices


def test_total_return_and_cagr():
    prices = sample_prices(periods=3)
    assert total_return(prices) == (102 / 100) - 1
    r = cagr(prices, periods_per_year=2)
    assert round(r, 6) == round((102 / 100) ** (1 / 1) - 1, 6)


def test_returns_table():
    prices = sample_prices()
    tbl = returns_table(prices)
    assert tbl.index == [2020]
    jan_ret = tbl["Jan"][0]
    assert round(jan_ret, 6) == round(130 / 100 - 1, 6)
    year_ret = tbl["Year"][0]
    assert round(year_ret, 6) == round(465 / 100 - 1, 6)


def test_rolling_cumulative_return():
    prices = sample_prices(periods=40)
    roll = rolling_cumulative_return(prices, window=30)
    assert roll.index == prices.index
    assert roll[30] == 130 / 100 - 1
    assert roll[31] == 131 / 101 - 1
