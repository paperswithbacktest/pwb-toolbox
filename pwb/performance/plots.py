import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from statistics import NormalDist


from .metrics import (
    _to_list,
    returns_table,
    annualized_volatility,
    parametric_var,
    sharpe_ratio,
    sortino_ratio,
    skewness,
    kurtosis,
    cumulative_excess_return,
    fama_french_3factor,
)


def plot_equity_curve(prices, logy: bool = True, ax=None):
    """Plot cumulative return equity curve."""
    if ax is None:
        fig, ax = plt.subplots()
    p = _to_list(prices)
    cum = [v / p[0] for v in p]
    ax.plot(getattr(prices, "index", range(len(p))), cum)
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Return")
    return ax


def plot_return_heatmap(prices, ax=None):
    """Plot calendar heatmap of returns from price series."""
    tbl = returns_table(prices)
    months = [c for c in tbl.columns if c != "Year"]
    data = tbl[months].astype(float).to_numpy()
    xtick_labels = months
    ytick_labels = tbl.index
    if ax is None:
        fig, ax = plt.subplots()
    im = ax.imshow(
        data,
        aspect="auto",
        interpolation="none",
        cmap="RdYlGn",
        vmin=float(np.nanmin(data)),
        vmax=float(np.nanmax(data)),
    )
    ax.set_yticks(range(len(tbl.index)))
    ax.set_yticklabels(tbl.index)
    ax.set_xticks(range(len(tbl.columns) - 1))
    ax.set_xticklabels([c for c in tbl.columns if c != "Year"])
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
    ax.plot(getattr(prices, "index", range(len(p))), dd)
    ax.set_ylabel("Drawdown")
    ax.set_xlabel("Date")
    return ax


def plot_rolling_volatility(
    prices, window: int = 63, periods_per_year: int = 252, ax=None
):
    """Plot rolling annualized volatility."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_volatility")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vols = []
    for i in range(len(p)):
        if i < window:
            vols.append(None)
        else:
            vols.append(annualized_volatility(p[i - window : i + 1], periods_per_year))
    s = pd.Series(vols)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("Volatility")
    ax.set_xlabel("Date")
    return ax


def plot_rolling_var(prices, window: int = 63, level: float = 0.05, ax=None):
    """Plot rolling parametric VaR."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_var")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vars_ = []
    for i in range(len(p)):
        if i < window:
            vars_.append(None)
        else:
            vars_.append(parametric_var(p[i - window : i + 1], level))
    s = pd.Series(vars_)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("VaR")
    ax.set_xlabel("Date")
    return ax


def plot_rolling_sharpe(
    prices,
    window: int = 63,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    ax=None,
):
    """Plot rolling Sharpe ratio."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_sharpe")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vals = []
    for i in range(len(p)):
        if i < window:
            vals.append(None)
        else:
            vals.append(
                sharpe_ratio(p[i - window : i + 1], risk_free_rate, periods_per_year)
            )
    s = pd.Series(vals)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("Sharpe")
    ax.set_xlabel("Date")
    return ax


def plot_rolling_sortino(
    prices,
    window: int = 63,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    ax=None,
):
    """Plot rolling Sortino ratio."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_sortino")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vals = []
    for i in range(len(p)):
        if i < window:
            vals.append(None)
        else:
            vals.append(
                sortino_ratio(p[i - window : i + 1], risk_free_rate, periods_per_year)
            )
    s = pd.Series(vals)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("Sortino")
    ax.set_xlabel("Date")
    return ax


def plot_return_scatter(prices, benchmark_prices, ax=None):
    """Scatter of strategy vs benchmark returns with regression line."""
    if pd is None:
        raise ImportError("pandas is required for plot_return_scatter")
    p = _to_list(prices)
    b = _to_list(benchmark_prices)
    n = min(len(p), len(b))
    if n < 2:
        raise ValueError("insufficient data")
    strat = [p[i] / p[i - 1] - 1 for i in range(1, n)]
    bench = [b[i] / b[i - 1] - 1 for i in range(1, n)]
    mean_x = sum(bench) / len(bench)
    mean_y = sum(strat) / len(strat)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(bench, strat)) / len(bench)
    var_x = sum((x - mean_x) ** 2 for x in bench) / len(bench)
    beta = cov / var_x if var_x else 0.0
    alpha = mean_y - beta * mean_x
    if ax is None:
        fig, ax = plt.subplots()
    ax.scatter(bench, strat, s=10)
    xs = [min(bench), max(bench)]
    ys = [alpha + beta * x for x in xs]
    ax.plot(xs, ys, color="red", label=f"alpha={alpha:.2f}, beta={beta:.2f}")
    ax.set_xlabel("Benchmark Return")
    ax.set_ylabel("Strategy Return")
    ax.legend()
    return ax


def plot_cumulative_excess_return(prices, benchmark_prices, ax=None):
    """Plot cumulative excess return versus benchmark."""
    if pd is None:
        raise ImportError("pandas is required for plot_cumulative_excess_return")
    ser = cumulative_excess_return(prices, benchmark_prices)
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(ser.index, ser)
    ax.set_ylabel("Cumulative Excess Return")
    ax.set_xlabel("Date")
    return ax


def plot_factor_exposures(prices, factors, ax=None):
    """Bar chart of Fama-French 3 factor exposures."""
    if pd is None:
        raise ImportError("pandas is required for plot_factor_exposures")
    exp = fama_french_3factor(prices, factors)
    names = [n for n in exp.index if n != "alpha"]
    vals = [exp[n] for n in names]
    if ax is None:
        fig, ax = plt.subplots()
    ax.bar(range(len(vals)), vals)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45)
    ax.set_ylabel("Exposure")
    return ax


def plot_trade_return_hist(trades, ax=None, bins=20):
    """Histogram of trade returns for long and short trades."""
    if ax is None:
        fig, ax = plt.subplots()
    longs = [t.get("return", 0) for t in trades if t.get("direction") == "long"]
    shorts = [t.get("return", 0) for t in trades if t.get("direction") == "short"]
    if longs:
        ax.hist(longs, bins=bins, alpha=0.5, label="Long")
    if shorts:
        ax.hist(shorts, bins=bins, alpha=0.5, label="Short")
    ax.set_xlabel("Trade Return")
    ax.set_ylabel("Frequency")
    if longs or shorts:
        ax.legend()
    return ax


def plot_return_by_holding_period(trades, ax=None):
    """Box plot of trade return grouped by holding period."""
    if ax is None:
        fig, ax = plt.subplots()
    groups = {}
    for t in trades:
        entry = t.get("entry")
        exit_ = t.get("exit")
        if entry is None or exit_ is None:
            continue
        dur = (
            (exit_ - entry).days
            if hasattr(exit_ - entry, "days")
            else int(exit_ - entry)
        )
        groups.setdefault(dur, []).append(t.get("return", 0))
    if not groups:
        return ax
    durations = sorted(groups)
    data = [groups[d] for d in durations]
    ax.boxplot(data, positions=range(len(data)))
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels([str(d) for d in durations])
    ax.set_xlabel("Holding Period (days)")
    ax.set_ylabel("Return")
    return ax


def plot_exposure_ts(trades, ax=None):
    """Time series of gross and net exposure based on open trades."""
    if pd is None:
        raise ImportError("pandas is required for plot_exposure_ts")
    entries = [t.get("entry") for t in trades if t.get("entry") is not None]
    exits = [t.get("exit") for t in trades if t.get("exit") is not None]
    if not entries or not exits:
        if ax is None:
            fig, ax = plt.subplots()
        return ax
    start = min(entries)
    end = max(exits)
    idx = pd.date_range(start, end)
    gross = [0.0 for _ in idx]
    net = [0.0 for _ in idx]
    for t in trades:
        entry = t.get("entry")
        exit_ = t.get("exit")
        size = t.get("size", 0.0)
        if entry is None or exit_ is None:
            continue
        for i, date in enumerate(idx):
            if entry <= date <= exit_:
                gross[i] += abs(size)
                net[i] += size
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(idx, gross, label="Gross")
    ax.plot(idx, net, label="Net")
    ax.set_ylabel("Exposure")
    ax.set_xlabel("Date")
    ax.legend()
    return ax


def plot_cumulative_shortfall(trades, ax=None):
    """Plot cumulative implementation shortfall over time."""
    if pd is None:
        raise ImportError("pandas is required for plot_cumulative_shortfall")

    from .trade_stats import trade_implementation_shortfall

    dates = []
    cum = []
    total = 0.0
    for t in trades:
        date = t.get("exit") or t.get("entry")
        total += trade_implementation_shortfall(t)
        dates.append(date)
        cum.append(total)

    ser = pd.Series(cum, index=dates)
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(ser.index, ser)
    ax.set_ylabel("Cumulative Shortfall")
    ax.set_xlabel("Date")
    return ax


def plot_alpha_vs_return(trades, ax=None):
    """Scatter plot of forecasted alpha versus realised trade return."""
    if pd is None:
        raise ImportError("pandas is required for plot_alpha_vs_return")

    alphas = [
        t.get("forecast_alpha") for t in trades if t.get("forecast_alpha") is not None
    ]
    rets = [t.get("return") for t in trades if t.get("forecast_alpha") is not None]

    if ax is None:
        fig, ax = plt.subplots()
    ax.scatter(alphas, rets, s=10)
    ax.set_xlabel("Forecast Alpha")
    ax.set_ylabel("Realized Return")
    return ax


def plot_qq_returns(prices, ax=None):
    """QQ-plot of returns versus normal distribution."""
    if ax is None:
        fig, ax = plt.subplots()
    p = _to_list(prices)
    if len(p) < 2:
        return ax
    rets = sorted(p[i] / p[i - 1] - 1 for i in range(1, len(p)))
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n
    std = var**0.5
    dist = NormalDist(mean, std)
    qs = [(i + 0.5) / n for i in range(n)]
    theo = [dist.inv_cdf(q) for q in qs]
    ax.scatter(theo, rets, s=10)
    ax.set_xlabel("Theoretical Quantiles")
    ax.set_ylabel("Empirical Quantiles")
    return ax


def plot_rolling_skewness(prices, window: int = 63, ax=None):
    """Plot rolling skewness of returns."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_skewness")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vals = []
    for i in range(len(p)):
        if i < window:
            vals.append(None)
        else:
            vals.append(skewness(p[i - window : i + 1]))
    s = pd.Series(vals)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("Skewness")
    ax.set_xlabel("Date")
    return ax


def plot_rolling_kurtosis(prices, window: int = 63, ax=None):
    """Plot rolling kurtosis of returns."""
    if pd is None:
        raise ImportError("pandas is required for plot_rolling_kurtosis")
    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    vals = []
    for i in range(len(p)):
        if i < window:
            vals.append(None)
        else:
            vals.append(kurtosis(p[i - window : i + 1]))
    s = pd.Series(vals)
    s.index = index
    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(s.index, s)
    ax.set_ylabel("Kurtosis")
    ax.set_xlabel("Date")
    return ax
