from __future__ import annotations

from typing import Dict, Iterable


class RiskManagementModel:
    """Base class for risk management models."""

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        """Return adjusted target weights based on risk rules."""
        raise NotImplementedError


class TrailingStopRiskManagementModel(RiskManagementModel):
    """Close positions if price falls a percentage from the peak."""

    def __init__(self, percent: float = 0.1):
        self.percent = percent
        self._highs: Dict[str, float] = {}

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        out = dict(weights)
        for symbol, weight in weights.items():
            price = prices.get(symbol)
            if price is None:
                continue
            high = self._highs.get(symbol, price)
            if price > high:
                high = price
            self._highs[symbol] = high
            if weight != 0 and price <= high * (1 - self.percent):
                out[symbol] = 0.0
        return out


class MaximumDrawdownPercentPerSecurity(TrailingStopRiskManagementModel):
    """Alias of trailing stop for per-security drawdown."""

    def __init__(self, max_drawdown: float = 0.1):
        super().__init__(percent=max_drawdown)


class MaximumDrawdownPercentPortfolio(RiskManagementModel):
    """Flatten portfolio if total drawdown exceeds a threshold."""

    def __init__(self, max_drawdown: float = 0.2):
        self.max_drawdown = max_drawdown
        self._high: float | None = None

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        nav = sum(weights.get(s, 0.0) * prices.get(s, 0.0) for s in weights)
        if self._high is None:
            self._high = nav
        if nav > self._high:
            self._high = nav
        if self._high and nav <= self._high * (1 - self.max_drawdown):
            return {s: 0.0 for s in weights}
        return weights


class MaximumUnrealizedProfitPercentPerSecurity(RiskManagementModel):
    """Take profit once unrealized gain exceeds threshold."""

    def __init__(self, max_profit: float = 0.2):
        self.max_profit = max_profit
        self._entry: Dict[str, float] = {}

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        out = dict(weights)
        for symbol, weight in weights.items():
            price = prices.get(symbol)
            if price is None:
                continue
            if weight == 0:
                self._entry.pop(symbol, None)
                continue
            entry = self._entry.get(symbol)
            if entry is None:
                self._entry[symbol] = price
                continue
            if weight > 0:
                profit = (price - entry) / entry
            else:
                profit = (entry - price) / entry
            if profit >= self.max_profit:
                out[symbol] = 0.0
                self._entry.pop(symbol, None)
        return out


class MaximumTotalPortfolioExposure(RiskManagementModel):
    """Scale weights so total gross exposure stays below a limit."""

    def __init__(self, max_exposure: float = 1.0):
        self.max_exposure = max_exposure

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float] | None = None) -> Dict[str, float]:
        gross = sum(abs(w) for w in weights.values())
        if gross <= self.max_exposure or gross == 0:
            return weights
        scale = self.max_exposure / gross
        return {s: w * scale for s, w in weights.items()}


class SectorExposureRiskManagementModel(RiskManagementModel):
    """Limit exposure by sector."""

    def __init__(self, sector_map: Dict[str, str], limit: float = 0.3):
        self.sector_map = sector_map
        self.limit = limit

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float] | None = None) -> Dict[str, float]:
        out = dict(weights)
        exposures: Dict[str, float] = {}
        for symbol, weight in weights.items():
            sector = self.sector_map.get(symbol)
            if sector is None:
                continue
            exposures[sector] = exposures.get(sector, 0.0) + abs(weight)
        for sector, exposure in exposures.items():
            if exposure > self.limit and exposure != 0:
                factor = self.limit / exposure
                for symbol, weight in weights.items():
                    if self.sector_map.get(symbol) == sector:
                        out[symbol] = weight * factor
        return out


class MaximumOrderQuantityPercentPerSecurity(RiskManagementModel):
    """Cap the change in weight for each security per evaluation call."""

    def __init__(self, max_percent: float = 0.1):
        self.max_percent = max_percent
        self._prev: Dict[str, float] = {}

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float] | None = None) -> Dict[str, float]:
        out = {}
        for symbol, target in weights.items():
            prev = self._prev.get(symbol, 0.0)
            diff = target - prev
            if diff > self.max_percent:
                new = prev + self.max_percent
            elif diff < -self.max_percent:
                new = prev - self.max_percent
            else:
                new = target
            out[symbol] = new
            self._prev[symbol] = new
        return out


class CompositeRiskManagementModel(RiskManagementModel):
    """Combine multiple risk models sequentially."""

    def __init__(self, models: Iterable[RiskManagementModel]):
        self.models = list(models)

    def evaluate(self, weights: Dict[str, float], prices: Dict[str, float]) -> Dict[str, float]:
        out = dict(weights)
        for model in self.models:
            out = model.evaluate(out, prices)
        return out


__all__ = [
    "RiskManagementModel",
    "TrailingStopRiskManagementModel",
    "MaximumDrawdownPercentPerSecurity",
    "MaximumDrawdownPercentPortfolio",
    "MaximumUnrealizedProfitPercentPerSecurity",
    "MaximumTotalPortfolioExposure",
    "SectorExposureRiskManagementModel",
    "MaximumOrderQuantityPercentPerSecurity",
    "CompositeRiskManagementModel",
]
