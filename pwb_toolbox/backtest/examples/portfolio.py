from __future__ import annotations

from typing import Dict, Iterable
import pandas as pd

from .shared import Insight, Direction
from ..portfolio_models import PortfolioConstructionModel

class EqualWeightPortfolio(PortfolioConstructionModel):
    """Allocate equal weight to all bullish/bearish insights."""

    def weights(self, insights: Iterable[Insight]) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active:
            return {}
        w = 1.0 / len(active)
        return {i.symbol: (w if i.direction == Direction.UP else -w) for i in active}


class VolatilityWeightPortfolio(PortfolioConstructionModel):
    """Weight positions by inverse volatility (simple risk parity)."""

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def weights(self, insights: Iterable[Insight], price_data: pd.DataFrame | None = None) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active or price_data is None:
            return {}
        vols = {}
        for ins in active:
            prices = price_data[ins.symbol]["close"] if (ins.symbol, "close") in price_data.columns else price_data[ins.symbol]
            if len(prices) < self.lookback:
                return {}
            vols[ins.symbol] = prices.pct_change().rolling(self.lookback).std().iloc[-1]
        inv_vol = {s: 1.0 / v for s, v in vols.items() if v > 0}
        total = sum(inv_vol.values())
        if total == 0:
            return {}
        return {
            s: (inv_vol[s] / total) * (1 if next(i for i in active if i.symbol == s).direction == Direction.UP else -1)
            for s in inv_vol
        }
