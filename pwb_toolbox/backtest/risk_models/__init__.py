from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Position:
    symbol: str
    quantity: float
    price: float
    entry_price: float
    sector: str = ""


class RiskManagementModel:
    """Base class for risk management models."""

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        """Return target weights after applying risk rules."""
        raise NotImplementedError


class TrailingStopRiskManagementModel(RiskManagementModel):
    def __init__(self, stop_percent: float):
        self.stop_percent = stop_percent
        self.high_prices: Dict[str, float] = {}

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        targets: Dict[str, float] = {}
        for p in positions:
            self.high_prices.setdefault(p.symbol, p.entry_price)
            self.high_prices[p.symbol] = max(self.high_prices[p.symbol], p.price)
            if p.price <= self.high_prices[p.symbol] * (1 - self.stop_percent):
                targets[p.symbol] = 0.0
            else:
                targets[p.symbol] = (p.quantity * p.price) / nav
        return targets


class MaximumDrawdownPercentPerSecurity(RiskManagementModel):
    def __init__(self, max_drawdown: float):
        self.max_drawdown = max_drawdown
        self.high_prices: Dict[str, float] = {}

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        targets: Dict[str, float] = {}
        for p in positions:
            self.high_prices.setdefault(p.symbol, p.entry_price)
            self.high_prices[p.symbol] = max(self.high_prices[p.symbol], p.price)
            dd = (p.price - self.high_prices[p.symbol]) / self.high_prices[p.symbol]
            if dd <= -self.max_drawdown:
                targets[p.symbol] = 0.0
            else:
                targets[p.symbol] = (p.quantity * p.price) / nav
        return targets


class MaximumDrawdownPercentPortfolio(RiskManagementModel):
    def __init__(self, max_drawdown: float):
        self.max_drawdown = max_drawdown
        self.high_nav: float | None = None

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions)
        if self.high_nav is None:
            self.high_nav = nav
        self.high_nav = max(self.high_nav, nav)
        dd = (nav - self.high_nav) / self.high_nav if self.high_nav else 0.0
        if dd <= -self.max_drawdown:
            return {p.symbol: 0.0 for p in positions}
        nav = nav or 1.0
        return {p.symbol: (p.quantity * p.price) / nav for p in positions}


class MaximumUnrealizedProfitPercentPerSecurity(RiskManagementModel):
    def __init__(self, max_profit: float):
        self.max_profit = max_profit

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        targets: Dict[str, float] = {}
        for p in positions:
            pnl = ((p.price - p.entry_price) / p.entry_price) * (1 if p.quantity > 0 else -1)
            if pnl >= self.max_profit:
                targets[p.symbol] = 0.0
            else:
                targets[p.symbol] = (p.quantity * p.price) / nav
        return targets


class MaximumTotalPortfolioExposure(RiskManagementModel):
    def __init__(self, max_exposure: float):
        self.max_exposure = max_exposure

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        weights = {p.symbol: (p.quantity * p.price) / nav for p in positions}
        gross = sum(abs(w) for w in weights.values())
        if gross <= self.max_exposure:
            return weights
        scale = self.max_exposure / gross
        return {s: w * scale for s, w in weights.items()}


class SectorExposureRiskManagementModel(RiskManagementModel):
    def __init__(self, sector_limit: float):
        self.sector_limit = sector_limit

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        weights = {p.symbol: (p.quantity * p.price) / nav for p in positions}
        sector_totals: Dict[str, float] = {}
        for p in positions:
            sector_totals[p.sector] = sector_totals.get(p.sector, 0) + abs(weights[p.symbol])
        targets = weights.copy()
        for sector, total in sector_totals.items():
            if total > self.sector_limit:
                scale = self.sector_limit / total
                for p in positions:
                    if p.sector == sector:
                        targets[p.symbol] *= scale
        return targets


class MaximumOrderQuantityPercentPerSecurity(RiskManagementModel):
    def __init__(self, max_weight: float):
        self.max_weight = max_weight

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        weights = {p.symbol: (p.quantity * p.price) / nav for p in positions}
        return {s: max(-self.max_weight, min(self.max_weight, w)) for s, w in weights.items()}


class CompositeRiskManagementModel(RiskManagementModel):
    def __init__(self, models: List[RiskManagementModel]):
        self.models = models

    def evaluate(self, positions: List[Position]) -> Dict[str, float]:
        nav = sum(p.quantity * p.price for p in positions) or 1.0
        weights = {p.symbol: (p.quantity * p.price) / nav for p in positions}
        current_positions = {p.symbol: p for p in positions}
        for model in self.models:
            # create Position objects based on current weights
            nav = sum(current_positions[s].price * current_positions[s].quantity for s in current_positions)
            new_positions = [
                Position(
                    symbol=s,
                    quantity=w * nav / current_positions[s].price,
                    price=current_positions[s].price,
                    entry_price=current_positions[s].entry_price,
                    sector=current_positions[s].sector,
                )
                for s, w in weights.items()
            ]
            weights = model.evaluate(new_positions)
            current_positions = {p.symbol: p for p in new_positions}
        return weights


__all__ = [
    "Position",
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
