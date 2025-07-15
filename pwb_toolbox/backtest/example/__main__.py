"""Minimal example showing how to run a backtest using the toolbox."""

from .alpha import GoldenCrossAlpha
from .portfolio import EqualWeightPortfolio
from .engine import run_backtest, run_ib_backtest
from .universe import StaticUniverse
from ..execution_models import ImmediateExecutionModel
from ..risk_models import MaximumTotalPortfolioExposure




def run_example():
    symbols = ["SPY", "QQQ"]
    universe = StaticUniverse(symbols)
    alpha = GoldenCrossAlpha()
    portfolio = EqualWeightPortfolio()
    execution = ImmediateExecutionModel()
    risk = MaximumTotalPortfolioExposure(max_exposure=1.0)
    result = run_backtest(
        universe,
        alpha,
        portfolio,
        execution=execution,
        risk=risk,
        start="2015-01-01",
    )
    print(result)


def run_ib_example():
    symbols = ["AAPL"]
    run_ib_backtest(symbols)


if __name__ == "__main__":
    run_example()
    # uncomment to test a simple Interactive Brokers run
    # run_ib_example()
