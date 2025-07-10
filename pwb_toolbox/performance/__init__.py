from .metrics import total_return, cagr, returns_table, rolling_cumulative_return

__all__ = [
    "total_return",
    "cagr",
    "returns_table",
    "rolling_cumulative_return",
]

try:  # pragma: no cover - optional plotting deps
    from .plots import plot_equity_curve, plot_return_heatmap

    __all__ += [
        "plot_equity_curve",
        "plot_return_heatmap",
    ]
except Exception:  # pragma: no cover - matplotlib may be missing
    pass
