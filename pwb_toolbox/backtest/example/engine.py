from __future__ import annotations

from datetime import date
from typing import Iterable

import backtrader as bt
import pandas as pd

from ...datasets import get_pricing
from .alpha import AlphaModel
from .portfolio import PortfolioConstructionModel
from .execution import rebalance
from ..ib_connector import run_ib_strategy


class ToolboxStrategy(bt.Strategy):
    params = (
        ("prices", None),
        ("alpha", None),
        ("portfolio", None),
    )

    def __init__(self):
        self.prices: pd.DataFrame = self.p.prices
        self.alpha: AlphaModel = self.p.alpha
        self.portfolio: PortfolioConstructionModel = self.p.portfolio

    def next(self):
        dt = bt.num2date(self.datas[0].datetime[0]).date()
        history = self.prices.loc[:dt]
        insights = self.alpha.generate(history)
        weights = self.portfolio.weights(insights, price_data=history)
        rebalance(self, weights)


class SimpleIBStrategy(bt.Strategy):
    """Example strategy for use with :func:`run_ib_strategy`."""

    def next(self):
        for data in self.datas:
            if data.close[0] > data.close[-1]:
                self.buy(data=data)
            elif data.close[0] < data.close[-1]:
                self.sell(data=data)


def run_backtest(
    symbols: Iterable[str],
    alpha: AlphaModel,
    portfolio: PortfolioConstructionModel,
    start: str = "2000-01-01",
    end: str | None = None,
    cash: float = 100000.0,
):
    """Convenience function to run a Backtrader backtest."""
    end = end or date.today().isoformat()
    prices = get_pricing(
        symbols, fields=["open", "high", "low", "close"], start_date=start, end_date=end
    )
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    for symbol in symbols:
        df = prices[symbol].copy()
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data, name=symbol)
    cerebro.addstrategy(
        ToolboxStrategy, prices=prices, alpha=alpha, portfolio=portfolio
    )
    return cerebro.run()


def run_ib_backtest(symbols: Iterable[str], **ib_kwargs):
    """Run :class:`SimpleIBStrategy` using Interactive Brokers data."""
    data_config = [{"dataname": s, "name": s} for s in symbols]
    return run_ib_strategy(SimpleIBStrategy, data_config, **ib_kwargs)
