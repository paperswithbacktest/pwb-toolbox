"""Minimal example showing how to run a backtest using the toolbox."""

from .alpha import GoldenCrossAlpha
from .portfolio import EqualWeightPortfolio
from .engine import run_backtest, run_ib_backtest
from .universe import StaticUniverse


def run_example():
    symbols = ["SPY", "QQQ"]
    universe = StaticUniverse(symbols)
    alpha = GoldenCrossAlpha()
    portfolio = EqualWeightPortfolio()
    run_backtest(universe.symbols(), alpha, portfolio, start="2015-01-01")


def run_ib_example():
    symbols = ["AAPL"]
    run_ib_backtest(symbols)


if __name__ == "__main__":
    run_example()
    # uncomment to test a simple Interactive Brokers run
    # run_ib_example()
