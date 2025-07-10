from .metrics import (
    total_return,
    cagr,
    returns_table,
    rolling_cumulative_return,
    annualized_volatility,
    max_drawdown,
    ulcer_index,
    ulcer_performance_index,
    parametric_var,
    parametric_expected_shortfall,
    tail_ratio,
)

__all__ = [
    "total_return",
    "cagr",
    "returns_table",
    "rolling_cumulative_return",
    "annualized_volatility",
    "max_drawdown",
    "ulcer_index",
    "ulcer_performance_index",
    "parametric_var",
    "parametric_expected_shortfall",
    "tail_ratio",
]

try:  # pragma: no cover - optional plotting deps
    from .plots import (
        plot_equity_curve,
        plot_return_heatmap,
        plot_underwater,
        plot_rolling_volatility,
        plot_rolling_var,
    )

    __all__ += [
        "plot_equity_curve",
        "plot_return_heatmap",
        "plot_underwater",
        "plot_rolling_volatility",
        "plot_rolling_var",
    ]
except Exception:  # pragma: no cover - matplotlib may be missing
    pass
