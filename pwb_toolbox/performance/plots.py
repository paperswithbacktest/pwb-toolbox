import matplotlib.pyplot as plt

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

from .metrics import _to_list, returns_table


def plot_equity_curve(prices, logy: bool = True, ax=None):
    """Plot cumulative return equity curve."""
    if ax is None:
        fig, ax = plt.subplots()
    p = _to_list(prices)
    cum = [v / p[0] for v in p]
    ax.plot(getattr(prices, 'index', range(len(p))), cum)
    if logy:
        ax.set_yscale('log')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative Return')
    return ax


def plot_return_heatmap(prices, ax=None):
    """Plot calendar heatmap of returns from price series."""
    if pd is None:
        raise ImportError("pandas is required for plot_return_heatmap")
    tbl = returns_table(prices)
    if ax is None:
        fig, ax = plt.subplots()
    data = [tbl[m].values for m in tbl.columns if m != 'Year']
    im = ax.imshow(data, aspect='auto', interpolation='none',
                   cmap='RdYlGn',
                   vmin=min((min(filter(None, row)) for row in data if any(row))),
                   vmax=max((max(filter(None, row)) for row in data if any(row))))
    ax.set_yticks(range(len(tbl.index)))
    ax.set_yticklabels(tbl.index)
    ax.set_xticks(range(len(tbl.columns)-1))
    ax.set_xticklabels([c for c in tbl.columns if c != 'Year'])
    plt.colorbar(im, ax=ax)
    return ax
