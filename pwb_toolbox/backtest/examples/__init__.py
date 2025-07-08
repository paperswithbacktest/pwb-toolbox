"""Example trading components for the backtest engine."""

from .shared import Direction, Insight
from .alpha import AlphaModel, GoldenCrossAlpha
from .portfolio import (
    PortfolioConstructionModel,
    EqualWeightPortfolio,
    VolatilityWeightPortfolio,
)
from .universe import Universe, StaticUniverse, SP500Universe
from .execution import rebalance
from .risk import max_drawdown, enforce_exposure_limit

__all__ = [
    "Direction",
    "Insight",
    "AlphaModel",
    "GoldenCrossAlpha",
    "PortfolioConstructionModel",
    "EqualWeightPortfolio",
    "VolatilityWeightPortfolio",
    "Universe",
    "StaticUniverse",
    "SP500Universe",
    "rebalance",
    "max_drawdown",
    "enforce_exposure_limit",
]
