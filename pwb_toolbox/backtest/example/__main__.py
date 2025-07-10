"""Minimal example showing how to run a backtest using the toolbox."""

from .alpha import GoldenCrossAlpha
from .portfolio import EqualWeightPortfolio
from .engine import run_backtest, run_ib_backtest
from .universe import StaticUniverse

from ...performance import total_return, cagr, plot_equity_curve
import matplotlib.pyplot as plt


def run_example():
    symbols = ["SPY", "QQQ"]
    universe = StaticUniverse(symbols)
    alpha = GoldenCrossAlpha()
    portfolio = EqualWeightPortfolio()
    # run_backtest now returns both the Backtrader result and an equity curve
    result, equity = run_backtest(
        universe.symbols(), alpha, portfolio, start="2015-01-01"
    )

    # basic performance metrics
    print(f"Total return: {total_return(equity):.2%}")
    print(f"CAGR: {cagr(equity):.2%}")

    # plot the equity curve
    plot_equity_curve(equity)
    plt.show()


def run_ib_example():
    symbols = ["AAPL"]
    run_ib_backtest(symbols)


if __name__ == "__main__":
    run_example()
    # uncomment to test a simple Interactive Brokers run
    # run_ib_example()
