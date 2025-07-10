from tests.stubs import pd, stub_environment

stub_environment()

from pwb_toolbox.performance import (
    capm_alpha_beta,
    fama_french_3factor,
    fama_french_5factor,
    cumulative_excess_return,
)


def sample_prices():
    idx = pd.date_range("2020-01-01", periods=7)
    prices = pd.Series([100, 102, 104, 103, 105, 107, 110])
    prices.index = idx
    return prices


def benchmark_prices():
    idx = pd.date_range("2020-01-01", periods=7)
    prices = pd.Series([100, 101, 100, 102, 103, 105, 107])
    prices.index = idx
    return prices


def factor_data():
    idx = pd.date_range("2020-01-01", periods=7)
    df = pd.DataFrame(
        {
            "Mkt-RF": [0.03, 0.02, -0.01, 0.015, 0.01, 0.012, 0.011],
            "SMB": [0.01, -0.005, 0.002, 0.003, 0.0, -0.001, 0.002],
            "HML": [0.005, 0.006, -0.004, 0.001, 0.002, -0.001, 0.003],
            "RMW": [0.002, 0.001, -0.002, 0.0005, 0.0003, 0.0007, 0.0002],
            "CMA": [0.004, -0.001, 0.001, 0.002, 0.001, 0.0005, -0.0003],
            "RF": [0.001] * 7,
        },
        index=idx,
    )
    return df


def test_capm_alpha_beta():
    a, b = capm_alpha_beta(sample_prices(), benchmark_prices())
    assert round(a, 6) == round(0.01941762150780434, 6)
    assert round(b, 6) == round(-0.2926922667006237, 6)


def test_fama_french_regressions():
    df = factor_data()
    ff3 = fama_french_3factor(sample_prices(), df)
    ff5 = fama_french_5factor(sample_prices(), df)
    assert round(ff3["alpha"], 6) == round(0.024946406188432135, 6)
    assert round(ff3["HML"], 6) == round(2.6652088456865646, 6)
    assert round(ff5["CMA"], 6) == round(-9.86975652880271, 6)


def test_cumulative_excess_return():
    ser = cumulative_excess_return(sample_prices(), benchmark_prices())
    assert len(ser) == 7
    assert round(ser[-1], 6) == round(0.0274876960860706, 6)
