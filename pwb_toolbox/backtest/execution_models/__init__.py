"""Execution models for order placement using Backtrader."""

from __future__ import annotations

from typing import Dict
import backtrader as bt


class ExecutionModel:
    """Base execution model class."""

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        """Place orders on the given strategy."""
        raise NotImplementedError


class ImmediateExecutionModel(ExecutionModel):
    """Immediately send market orders using ``order_target_percent``."""

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        for data in strategy.datas:
            target = weights.get(data._name, 0.0)
            strategy.order_target_percent(data=data, target=target)


class StandardDeviationExecutionModel(ExecutionModel):
    """Only trade when recent volatility exceeds a threshold."""

    def __init__(self, lookback: int = 20, threshold: float = 0.01):
        self.lookback = lookback
        self.threshold = threshold

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        prices = strategy.prices
        for data in strategy.datas:
            symbol = data._name
            series = prices[symbol]["close"] if (symbol, "close") in prices.columns else prices[symbol]
            if len(series) < self.lookback:
                continue
            vol = series.pct_change().rolling(self.lookback).std().iloc[-1]
            if vol is not None and vol > self.threshold:
                target = weights.get(symbol, 0.0)
                strategy.order_target_percent(data=data, target=target)


class VolumeWeightedAveragePriceExecutionModel(ExecutionModel):
    """Split orders evenly over a number of steps to approximate VWAP."""

    def __init__(self, steps: int = 3):
        self.steps = steps
        self._progress: Dict[str, int] = {}

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        for data in strategy.datas:
            symbol = data._name
            step = self._progress.get(symbol, 0)
            if step >= self.steps:
                continue
            target = weights.get(symbol, 0.0) * (step + 1) / self.steps
            strategy.order_target_percent(data=data, target=target)
            self._progress[symbol] = step + 1


class VolumePercentageExecutionModel(ExecutionModel):
    """Execute only a percentage of the target each call."""

    def __init__(self, percentage: float = 0.25):
        self.percentage = percentage
        self._filled: Dict[str, float] = {}

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        for data in strategy.datas:
            symbol = data._name
            current = self._filled.get(symbol, 0.0)
            target = weights.get(symbol, 0.0)
            remaining = target - current
            if abs(remaining) < 1e-6:
                continue
            step_target = current + remaining * self.percentage
            self._filled[symbol] = step_target
            strategy.order_target_percent(data=data, target=step_target)


class TimeProfileExecutionModel(ExecutionModel):
    """Execute orders based on a predefined time profile (e.g. TWAP)."""

    def __init__(self, profile: Dict[int, float] | None = None):
        self.profile = profile or {0: 1.0}
        self._called = 0

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        factor = self.profile.get(self._called, 0.0)
        for data in strategy.datas:
            target = weights.get(data._name, 0.0) * factor
            strategy.order_target_percent(data=data, target=target)
        self._called += 1


class TrailingLimitExecutionModel(ExecutionModel):
    """Use trailing limit orders for execution."""

    def __init__(self, trail: float = 0.01):
        self.trail = trail

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        prices = strategy.prices
        for data in strategy.datas:
            symbol = data._name
            price = prices[symbol]["close"].iloc[-1] if (symbol, "close") in prices.columns else prices[symbol].iloc[-1]
            target = weights.get(symbol, 0.0)
            if target > 0:
                strategy.buy(data=data, exectype=bt.Order.Limit, price=price * (1 - self.trail))
            elif target < 0:
                strategy.sell(data=data, exectype=bt.Order.Limit, price=price * (1 + self.trail))


class AdaptiveExecutionModel(ExecutionModel):
    """Switch between immediate and VWAP execution based on volatility."""

    def __init__(self, threshold: float = 0.02, steps: int = 3):
        self.threshold = threshold
        self.vwap = VolumeWeightedAveragePriceExecutionModel(steps=steps)
        self.immediate = ImmediateExecutionModel()

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        prices = strategy.prices
        for data in strategy.datas:
            symbol = data._name
            series = prices[symbol]["close"] if (symbol, "close") in prices.columns else prices[symbol]
            if len(series) < 2:
                continue
            vol = series.pct_change().iloc[-1]
            if abs(vol) > self.threshold:
                self.immediate.execute(strategy, {symbol: weights.get(symbol, 0.0)})
            else:
                self.vwap.execute(strategy, {symbol: weights.get(symbol, 0.0)})


class BufferedExecutionModel(ExecutionModel):
    """Only execute when target differs sufficiently from last order."""

    def __init__(self, buffer: float = 0.05):
        self.buffer = buffer
        self._last: Dict[str, float] = {}

    def execute(self, strategy: bt.Strategy, weights: Dict[str, float]):
        for data in strategy.datas:
            symbol = data._name
            target = weights.get(symbol, 0.0)
            last = self._last.get(symbol)
            if last is None or abs(target - last) > self.buffer:
                strategy.order_target_percent(data=data, target=target)
                self._last[symbol] = target
