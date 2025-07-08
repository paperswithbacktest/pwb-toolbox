from __future__ import annotations

from typing import Dict
import backtrader as bt


def rebalance(strategy: bt.Strategy, weights: Dict[str, float]):
    """Apply target weights using Backtrader order APIs."""
    for data in strategy.datas:
        target = weights.get(data._name, 0.0)
        strategy.order_target_percent(data=data, target=target)
