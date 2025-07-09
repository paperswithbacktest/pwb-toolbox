from tests.stubs import pd, stub_environment

stub_environment()


def test_run_backtest():
    from pwb_toolbox.backtest import run_backtest
    from pwb_toolbox.backtest.examples import GoldenCrossAlpha, EqualWeightPortfolio

    result = run_backtest(["SPY"], GoldenCrossAlpha(), EqualWeightPortfolio(), start="2020-01-01")
    assert result == ["ok"]

