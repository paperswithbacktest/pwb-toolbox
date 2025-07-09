from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable
import numpy as np
import pandas as pd

from .. import Insight, Direction


class PortfolioConstructionModel(ABC):
    """Abstract base class for portfolio construction models."""

    @abstractmethod
    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        """Return target weights for each symbol."""
        pass


class EqualWeightingPortfolioConstructionModel(PortfolioConstructionModel):
    """Allocate equal weight to all non-flat insights."""

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active:
            return {}
        w = 1.0 / len(active)
        return {i.symbol: (w if i.direction == Direction.UP else -w) for i in active}


class InsightWeightingPortfolioConstructionModel(PortfolioConstructionModel):
    """Weight positions according to insight weight attribute."""

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active:
            return {}
        total = sum(abs(i.weight) for i in active)
        if total == 0:
            return {}
        return {
            i.symbol: (i.weight / total) * (1 if i.direction == Direction.UP else -1)
            for i in active
        }


class RiskParityPortfolioConstructionModel(PortfolioConstructionModel):
    """Simple risk parity based on inverse volatility."""

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active or price_data is None:
            return {}
        vols = {}
        for ins in active:
            prices = (
                price_data[ins.symbol]["close"]
                if (ins.symbol, "close") in price_data.columns
                else price_data[ins.symbol]
            )
            if len(prices) < self.lookback:
                return {}
            vols[ins.symbol] = prices.pct_change().rolling(self.lookback).std().iloc[-1]
        inv_vol = {s: 1.0 / v for s, v in vols.items() if v > 0}
        total = sum(inv_vol.values())
        if total == 0:
            return {}
        return {
            s: (inv_vol[s] / total)
            * (
                1
                if next(i for i in active if i.symbol == s).direction == Direction.UP
                else -1
            )
            for s in inv_vol
        }


class MeanVarianceOptimizationPortfolioConstructionModel(PortfolioConstructionModel):
    """Mean-variance optimization with weight normalization."""

    def __init__(self, lookback: int = 60):
        self.lookback = lookback

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active or price_data is None:
            return {}
        symbols = [i.symbol for i in active]
        df = price_data[symbols]
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs("close", axis=1, level=-1)
        if len(df) < self.lookback:
            return {}
        rets = df.pct_change().dropna()
        mu = rets.mean()
        cov = rets.cov()
        inv_cov = np.linalg.pinv(cov.values)
        exp = np.array(
            [
                mu[s]
                * (
                    1
                    if next(i for i in active if i.symbol == s).direction
                    == Direction.UP
                    else -1
                )
                for s in mu.index
            ]
        )
        raw = inv_cov.dot(exp)
        total = np.sum(np.abs(raw))
        if total == 0:
            return {}
        w = raw / total
        return {s: float(w[i]) for i, s in enumerate(mu.index)}


class UnconstrainedMeanVariancePortfolioConstructionModel(PortfolioConstructionModel):
    """Mean-variance optimization without normalization of weights."""

    def __init__(self, lookback: int = 60):
        self.lookback = lookback

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active or price_data is None:
            return {}
        symbols = [i.symbol for i in active]
        df = price_data[symbols]
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs("close", axis=1, level=-1)
        if len(df) < self.lookback:
            return {}
        rets = df.pct_change().dropna()
        mu = rets.mean()
        cov = rets.cov()
        inv_cov = np.linalg.pinv(cov.values)
        exp = np.array(
            [
                mu[s]
                * (
                    1
                    if next(i for i in active if i.symbol == s).direction
                    == Direction.UP
                    else -1
                )
                for s in mu.index
            ]
        )
        raw = inv_cov.dot(exp)
        return {s: float(raw[i]) for i, s in enumerate(mu.index)}


class BlackLittermanOptimizationPortfolioConstructionModel(
    MeanVarianceOptimizationPortfolioConstructionModel
):
    """Simplified Black-Litterman model using a blend of market and view returns."""

    def __init__(self, lookback: int = 60, view_weight: float = 0.5):
        super().__init__(lookback)
        self.view_weight = view_weight

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active or price_data is None:
            return {}
        symbols = [i.symbol for i in active]
        df = price_data[symbols]
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs("close", axis=1, level=-1)
        if len(df) < self.lookback:
            return {}
        rets = df.pct_change().dropna()
        market_mu = rets.mean()
        view_mu = pd.Series(
            {i.symbol: (1 if i.direction == Direction.UP else -1) for i in active}
        )
        mu = (1 - self.view_weight) * market_mu + self.view_weight * view_mu
        cov = rets.cov()
        inv_cov = np.linalg.pinv(cov.values)
        exp = mu.loc[market_mu.index].values
        raw = inv_cov.dot(exp)
        total = np.sum(np.abs(raw))
        if total == 0:
            return {}
        w = raw / total
        return {s: float(w[i]) for i, s in enumerate(market_mu.index)}


class TargetPercentagePortfolioConstructionModel(PortfolioConstructionModel):
    """Return predefined target portfolio percentages."""

    def __init__(self, targets: Dict[str, float]):
        self.targets = targets

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active_symbols = {
            i.symbol: i for i in insights if i.direction != Direction.FLAT
        }
        return {
            s: (
                self.targets.get(s, 0.0)
                * (1 if active_symbols[s].direction == Direction.UP else -1)
            )
            for s in active_symbols
            if s in self.targets
        }


class DollarCostAveragingPortfolioConstructionModel(PortfolioConstructionModel):
    """Allocate a fixed percentage to each new insight."""

    def __init__(self, allocation: float = 0.1):
        self.allocation = allocation

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        active = [i for i in insights if i.direction != Direction.FLAT]
        if not active:
            return {}
        return {
            i.symbol: self.allocation * (1 if i.direction == Direction.UP else -1)
            for i in active
        }


class InsightRatioPortfolioConstructionModel(PortfolioConstructionModel):
    """Scale long and short exposure by the ratio of insights."""

    def weights(
        self,
        insights: Iterable[Insight],
        price_data: pd.DataFrame | None = None,
    ) -> Dict[str, float]:
        ups = [i for i in insights if i.direction == Direction.UP]
        downs = [i for i in insights if i.direction == Direction.DOWN]
        total = len(ups) + len(downs)
        if total == 0:
            return {}
        up_share = len(ups) / total
        down_share = len(downs) / total
        weights = {}
        if ups:
            per = up_share / len(ups)
            for i in ups:
                weights[i.symbol] = per
        if downs:
            per = down_share / len(downs)
            for i in downs:
                weights[i.symbol] = -per
        return weights
