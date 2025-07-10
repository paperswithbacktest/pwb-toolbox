from tests.stubs import pd, stub_environment

stub_environment()

from pwb_toolbox.performance import (
    skewness,
    kurtosis,
    variance_ratio,
    acf,
    pacf,
)


def sample_prices():
    idx = pd.date_range("2020-01-01", periods=6)
    prices = pd.Series([100, 110, 105, 115, 90, 95])
    prices.index = idx
    return prices


def test_distribution_metrics():
    prices = sample_prices()
    sk = skewness(prices)
    ku = kurtosis(prices)
    vr = variance_ratio(prices, lag=2)
    ac = acf(prices, [1, 2, 3])
    pa = pacf(prices, [1, 2, 3])

    assert round(sk, 6) == round(-0.9149873089234433, 6)
    assert round(ku, 6) == round(2.303037046271514, 6)
    assert round(vr, 6) == round(0.23643688216297953, 6)
    assert [round(v, 6) for v in ac] == [
        round(-0.7358971666090506, 6),
        round(0.5811341547375707, 6),
        round(-0.8576078755720586, 6),
    ]
    assert [round(v, 6) for v in pa] == [
        round(-0.6475516186964594, 6),
        round(2.310668133331484, 6),
        0.0,
    ]


