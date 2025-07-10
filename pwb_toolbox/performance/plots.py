import matplotlib.pyplot as plt

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

from .metrics import (
    _to_list,
    returns_table,
    annualized_volatility,
    parametric_var,
)


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


def plot_underwater(prices, ax=None):
    """Plot drawdown (underwater) chart."""
    if ax is None:
        fig, ax = plt.subplots()
    p = _to_list(prices)
    peak = p[0] if p else 0
    dd = []
    for price in p:
        if price > peak:
            peak = price
        dd.append(price / peak - 1)
    ax.plot(getattr(prices, 'index', range(len(p))), dd)
    ax.set_ylabel('Drawdown')
    ax.set_xlabel('Date')
    return ax


def plot_rolling_volatility(prices, window: int = 63, periods_per_year: int = 252, ax=None):
    """Plot rolling annualized volatility."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_volatility")
    p = _to_list(prices)
    index = list(getattr(prices, 'index', range(len(p))))
    vols = []
    for i in range(len(p)):
        if i < window:
            vols.append(None)
        else:
            vols.append(annualized_volatility(p[i - window:i + 1], periods_per_year))
    s = pd.Series(vols)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel('Volatility')
    ax.set_xlabel('Date')
    return ax


def plot_rolling_var(prices, window: int = 63, level: float = 0.05, ax=None):
    """Plot rolling parametric VaR."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_var")
    p = _to_list(prices)
    index = list(getattr(prices, 'index', range(len(p))))
    vars_ = []
    for i in range(len(p)):
        if i < window:
            vars_.append(None)
        else:
            vars_.append(parametric_var(p[i - window:i + 1], level))
    s = pd.Series(vars_)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel('VaR')
    ax.set_xlabel('Date')
    return ax
