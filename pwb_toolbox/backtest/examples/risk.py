from __future__ import annotations

import pandas as pd


def max_drawdown(nav: pd.Series) -> float:
    """Compute maximum drawdown of a NAV series."""
    rolling_max = nav.cummax()
    drawdown = (nav - rolling_max) / rolling_max
    return drawdown.min()


def enforce_exposure_limit(weights: dict[str, float], limit: float) -> dict[str, float]:
    """Scale weights so gross exposure stays below limit."""
    gross = sum(abs(w) for w in weights.values())
    if gross <= limit:
        return weights
    scale = limit / gross
    return {k: v * scale for k, v in weights.items()}
