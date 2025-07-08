from __future__ import annotations

import pandas as pd

from .shared import Insight, Direction


class AlphaModel:
    """Base class for alpha models."""

    def generate(self, data: pd.DataFrame) -> list[Insight]:
        """Return a list of Insight objects."""
        raise NotImplementedError


class GoldenCrossAlpha(AlphaModel):
    """Simple moving average crossover model."""

    def __init__(self, fast: int = 50, slow: int = 200):
        self.fast = fast
        self.slow = slow

    def generate(self, data: pd.DataFrame) -> list[Insight]:
        insights: list[Insight] = []
        for symbol in data.columns.get_level_values(0).unique():
            prices = data[symbol]["close"] if (symbol, "close") in data.columns else data[symbol]
            if len(prices) < self.slow:
                continue
            fast_ma = prices.rolling(self.fast).mean()
            slow_ma = prices.rolling(self.slow).mean()
            if pd.isna(fast_ma.iloc[-2]) or pd.isna(slow_ma.iloc[-2]):
                continue
            if fast_ma.iloc[-2] < slow_ma.iloc[-2] and fast_ma.iloc[-1] > slow_ma.iloc[-1]:
                insights.append(Insight(symbol, Direction.UP, prices.index[-1]))
            elif fast_ma.iloc[-2] > slow_ma.iloc[-2] and fast_ma.iloc[-1] < slow_ma.iloc[-1]:
                insights.append(Insight(symbol, Direction.DOWN, prices.index[-1]))
        return insights
