from __future__ import annotations

from datetime import date
from typing import Iterable

import backtrader as bt
import pandas as pd

from ...datasets import get_pricing
from .alpha import AlphaModel
from .portfolio import PortfolioConstructionModel
from ..execution_models import ExecutionModel, ImmediateExecutionModel
from ..risk_models import RiskManagementModel
from ..universe_models import UniverseSelectionModel
from .execution import rebalance
from ..ib_connector import run_ib_strategy


class ToolboxStrategy(bt.Strategy):
    params = (
        ("prices", None),
        ("alpha", None),
        ("portfolio", None),
        ("execution", None),
        ("risk", None),
        ("universe", None),
    )

    def __init__(self):
        self.prices: pd.DataFrame = self.p.prices
        self.alpha: AlphaModel = self.p.alpha
        self.portfolio: PortfolioConstructionModel = self.p.portfolio
        self.execution: ExecutionModel | None = (
            self.p.execution or ImmediateExecutionModel()
        )
        self.risk: RiskManagementModel | None = self.p.risk
        self.universe: UniverseSelectionModel | None = self.p.universe

    def next(self):
        dt = bt.num2date(self.datas[0].datetime[0]).date()
        history = self.prices.loc[:dt]
        if self.universe is not None:
            active = self.universe.symbols(dt)
            if isinstance(history.columns, pd.MultiIndex):
                history = history[active]
            else:
                history = history[active]
        else:
            active = [d._name for d in self.datas]
        insights = self.alpha.generate(history)
        weights = self.portfolio.weights(insights, price_data=history)
        if self.risk is not None:
            prices = {}
            for s in active:
                if (s, "close") in history.columns:
                    prices[s] = history[s]["close"].iloc[-1]
                elif s in history.columns:
                    prices[s] = history[s].iloc[-1]
            weights = self.risk.evaluate(weights, prices)
        if self.execution is not None:
            self.execution.execute(self, weights)
        else:
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
    universe: UniverseSelectionModel,
    alpha: AlphaModel,
    portfolio: PortfolioConstructionModel,
    execution: ExecutionModel | None = None,
    risk: RiskManagementModel | None = None,
    start: str = "2000-01-01",
    end: str | None = None,
    cash: float = 100000.0,
):
    """Convenience function to run a Backtrader backtest."""
    end = end or date.today().isoformat()
    symbols = universe.symbols()
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
        ToolboxStrategy,
        prices=prices,
        alpha=alpha,
        portfolio=portfolio,
        execution=execution,
        risk=risk,
        universe=universe,
    )
    return cerebro.run()


def run_ib_backtest(symbols: Iterable[str], **ib_kwargs):
    """Run :class:`SimpleIBStrategy` using Interactive Brokers data."""
    data_config = [{"dataname": s, "name": s} for s in symbols]
    return run_ib_strategy(SimpleIBStrategy, data_config, **ib_kwargs)
