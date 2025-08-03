from calendar import month_abbr
from typing import Sequence, Tuple
from math import sqrt
from statistics import NormalDist

import pandas as pd


def _to_list(data: Sequence[float]) -> list:
    """Convert Series-like data to list."""
    if hasattr(data, "values"):
        return list(data.values)
    return list(data)


def total_return(prices: Sequence[float]) -> float:
    """Return total return of a price series."""
    p = _to_list(prices)
    if not p:
        return 0.0
    return p[-1] / p[0] - 1


def cagr(prices: Sequence[float], periods_per_year: int = 252) -> float:
    """Compound annual growth rate from a price series."""
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0
    years = (len(p) - 1) / periods_per_year
    if years == 0:
        return 0.0
    return (p[-1] / p[0]) ** (1 / years) - 1


def returns_table(prices: "pd.Series") -> "pd.DataFrame":  # type: ignore
    """Return monthly and yearly percentage returns from a daily price series."""
    if pd is None:
        raise ImportError("pandas is required for returns_table")

    price_list = _to_list(prices)
    index = list(getattr(prices, "index", range(len(price_list))))

    years = sorted({dt.year for dt in index})
    months = list(range(1, 13))
    data = {month_abbr[m]: [] for m in months}
    data["Year"] = []

    for year in years:
        year_start = None
        year_end = None
        for m in months:
            # indices belonging to year & month
            idx = [i for i, dt in enumerate(index) if dt.year == year and dt.month == m]
            if idx:
                start = idx[0]
                end = idx[-1]
                ret = price_list[end] / price_list[start] - 1
                if year_start is None:
                    year_start = price_list[start]
                year_end = price_list[end]
            else:
                ret = None
            data[month_abbr[m]].append(ret)
        if year_start is None:
            data["Year"].append(None)
        else:
            data["Year"].append(year_end / year_start - 1)

    return pd.DataFrame(data, index=years)


def rolling_cumulative_return(prices: "pd.Series", window: int) -> "pd.Series":  # type: ignore
    """Rolling cumulative return over a specified window."""
    if pd is None:
        raise ImportError("pandas is required for rolling_cumulative_return")

    p = _to_list(prices)
    index = list(getattr(prices, "index", range(len(p))))
    out = []
    for i in range(len(p)):
        if i < window:
            out.append(None)
        else:
            out.append(p[i] / p[i - window] - 1)
    s = pd.Series(out)
    s.index = index
    return s


def annualized_volatility(
    prices: Sequence[float], periods_per_year: int = 252
) -> float:
    """Annualized volatility from a price series."""
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return sqrt(var) * sqrt(periods_per_year)


def max_drawdown(prices: Sequence[float]) -> Tuple[float, int]:
    """Maximum drawdown depth and duration."""
    p = _to_list(prices)
    if not p:
        return 0.0, 0
    peak = p[0]
    max_depth = 0.0
    duration = 0
    cur_duration = 0
    for price in p:
        if price > peak:
            peak = price
            cur_duration = 0
        else:
            cur_duration += 1
            dd = price / peak - 1
            if dd < max_depth:
                max_depth = dd
        if cur_duration > duration:
            duration = cur_duration
    return max_depth, duration


def ulcer_index(prices: Sequence[float]) -> float:
    """Ulcer index of a price series."""
    p = _to_list(prices)
    if not p:
        return 0.0
    peak = p[0]
    sum_sq = 0.0
    for price in p:
        if price > peak:
            peak = price
        dd = max(0.0, (peak - price) / peak)
        sum_sq += dd**2
    return sqrt(sum_sq / len(p))


def ulcer_performance_index(
    prices: Sequence[float], risk_free_rate: float = 0.0, periods_per_year: int = 252
) -> float:
    """Ulcer Performance Index."""
    ui = ulcer_index(prices)
    if ui == 0:
        return 0.0
    return (cagr(prices, periods_per_year) - risk_free_rate) / ui


def _parametric_stats(prices: Sequence[float]) -> Tuple[float, float]:
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0, 0.0
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / len(rets)
    return mu, sqrt(var)


def parametric_var(prices: Sequence[float], level: float = 0.05) -> float:
    """Parametric (normal) Value at Risk."""
    mu, sigma = _parametric_stats(prices)
    z = NormalDist().inv_cdf(level)
    return -(mu + sigma * z)


def parametric_expected_shortfall(
    prices: Sequence[float], level: float = 0.05
) -> float:
    """Parametric (normal) Expected Shortfall."""
    mu, sigma = _parametric_stats(prices)
    z = NormalDist().inv_cdf(level)
    return -(mu - sigma * NormalDist().pdf(z) / level)


def tail_ratio(prices: Sequence[float]) -> float:
    """Tail ratio of returns (95th percentile over 5th percentile)."""
    p = _to_list(prices)
    if len(p) < 3:
        return 0.0
    rets = sorted(p[i] / p[i - 1] - 1 for i in range(1, len(p)))
    n = len(rets)
    q95 = rets[int(0.95 * (n - 1))]
    q05 = rets[int(0.05 * (n - 1))]
    if q05 == 0:
        return 0.0
    return abs(q95) / abs(q05)


def sharpe_ratio(
    prices: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sharpe ratio of a price series."""
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0
    rf_per = risk_free_rate / periods_per_year
    rets = [p[i] / p[i - 1] - 1 - rf_per for i in range(1, len(p)) if p[i - 1] > 0]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    if var == 0:
        return 0.0
    return mean / sqrt(var) * sqrt(periods_per_year)


def sortino_ratio(
    prices: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sortino ratio of a price series."""
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0
    rf_per = risk_free_rate / periods_per_year
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean_excess = sum(r - rf_per for r in rets) / len(rets)
    downside = [min(0.0, r - rf_per) for r in rets]
    var = sum(d**2 for d in downside) / len(rets)
    if var == 0:
        return 0.0
    return mean_excess / sqrt(var) * sqrt(periods_per_year)


def calmar_ratio(prices: Sequence[float], periods_per_year: int = 252) -> float:
    """Calmar ratio of a price series."""
    mdd, _duration = max_drawdown(prices)
    if mdd == 0:
        return 0.0
    return cagr(prices, periods_per_year) / abs(mdd)


def omega_ratio(
    prices: Sequence[float],
    threshold: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Omega ratio of returns relative to a threshold."""
    p = _to_list(prices)
    if len(p) < 2:
        return 0.0
    thr = threshold / periods_per_year
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    gains = sum(max(r - thr, 0.0) for r in rets)
    losses = sum(max(thr - r, 0.0) for r in rets)
    if losses == 0:
        return 0.0
    return gains / losses


def information_ratio(
    prices: Sequence[float],
    benchmark: Sequence[float],
    periods_per_year: int = 252,
) -> float:
    """Information ratio of strategy vs. benchmark prices."""
    p = _to_list(prices)
    b = _to_list(benchmark)
    n = min(len(p), len(b))
    if n < 2:
        return 0.0
    strat_rets = [p[i] / p[i - 1] - 1 for i in range(1, n)]
    bench_rets = [b[i] / b[i - 1] - 1 for i in range(1, n)]
    active = [r - br for r, br in zip(strat_rets, bench_rets)]
    mean = sum(active) / len(active)
    var = sum((a - mean) ** 2 for a in active) / len(active)
    if var == 0:
        return 0.0
    return mean / sqrt(var) * sqrt(periods_per_year)


def capm_alpha_beta(
    prices: Sequence[float], benchmark: Sequence[float]
) -> Tuple[float, float]:
    """CAPM alpha and beta relative to a benchmark."""
    p = _to_list(prices)
    b = _to_list(benchmark)
    n = min(len(p), len(b))
    if n < 2:
        return 0.0, 0.0
    strat = [p[i] / p[i - 1] - 1 for i in range(1, n)]
    bench = [b[i] / b[i - 1] - 1 for i in range(1, n)]
    mean_x = sum(bench) / len(bench)
    mean_y = sum(strat) / len(strat)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(bench, strat)) / len(bench)
    var_x = sum((x - mean_x) ** 2 for x in bench) / len(bench)
    beta = cov / var_x if var_x else 0.0
    alpha = mean_y - beta * mean_x
    return alpha, beta


def _invert_matrix(
    matrix: Sequence[Sequence[float]],
) -> Sequence[Sequence[float]] | None:
    size = len(matrix)
    aug = [
        list(row) + [1 if i == j else 0 for j in range(size)]
        for i, row in enumerate(matrix)
    ]
    for i in range(size):
        pivot = aug[i][i]
        if abs(pivot) < 1e-12:
            swap = next((j for j in range(i + 1, size) if abs(aug[j][i]) > 1e-12), None)
            if swap is None:
                return None
            aug[i], aug[swap] = aug[swap], aug[i]
            pivot = aug[i][i]
        inv_p = 1 / pivot
        for j in range(2 * size):
            aug[i][j] *= inv_p
        for k in range(size):
            if k != i:
                factor = aug[k][i]
                for j in range(2 * size):
                    aug[k][j] -= factor * aug[i][j]
    return [row[size:] for row in aug]


def _ols(y: Sequence[float], X: Sequence[Sequence[float]]) -> Sequence[float]:
    n = len(y)
    k = len(X[0]) if X else 0
    xtx = [[0.0 for _ in range(k)] for _ in range(k)]
    xty = [0.0 for _ in range(k)]
    for i in range(n):
        for p in range(k):
            xty[p] += X[i][p] * y[i]
            for q in range(k):
                xtx[p][q] += X[i][p] * X[i][q]
    inv = _invert_matrix(xtx)
    if inv is None:
        return [0.0 for _ in range(k)]
    beta = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    return beta


def fama_french_regression(prices: Sequence[float], factors: "pd.DataFrame", factor_cols: Sequence[str]) -> "pd.Series":  # type: ignore
    """Run regression of excess returns on Fama-French factors."""
    if pd is None:
        raise ImportError("pandas is required for fama_french_regression")

    p = _to_list(prices)
    n = min(len(p), len(factors))
    if n < 2:
        data = [0.0] * (len(factor_cols) + 1)
        s = pd.Series(data)
        s.index = ["alpha"] + list(factor_cols)
        return s

    rets = [p[i] / p[i - 1] - 1 for i in range(1, n)]
    rf = _to_list(factors["RF"]) if "RF" in factors.columns else [0.0] * n
    y = [rets[i - 1] - rf[i] for i in range(1, n)]
    x = [[1.0] + [_to_list(factors[c])[i] for c in factor_cols] for i in range(1, n)]
    beta = _ols(y, x)
    s = pd.Series(beta)
    s.index = ["alpha"] + list(factor_cols)
    return s


def fama_french_3factor(prices: Sequence[float], factors: "pd.DataFrame") -> "pd.Series":  # type: ignore
    cols = [c for c in ["Mkt-RF", "SMB", "HML"] if c in getattr(factors, "columns", [])]
    return fama_french_regression(prices, factors, cols)


def fama_french_5factor(prices: Sequence[float], factors: "pd.DataFrame") -> "pd.Series":  # type: ignore
    cols = [
        c
        for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
        if c in getattr(factors, "columns", [])
    ]
    return fama_french_regression(prices, factors, cols)


def cumulative_excess_return(prices: Sequence[float], benchmark: Sequence[float]) -> "pd.Series":  # type: ignore
    """Cumulative excess return of strategy versus a benchmark."""
    if pd is None:
        raise ImportError("pandas is required for cumulative_excess_return")

    p = _to_list(prices)
    b = _to_list(benchmark)
    n = min(len(p), len(b))
    index = list(getattr(prices, "index", range(len(p))))[:n]
    cum = []
    total = 1.0
    for i in range(n):
        if i == 0:
            cum.append(0.0)
        else:
            strat_ret = p[i] / p[i - 1] - 1
            bench_ret = b[i] / b[i - 1] - 1
            total *= 1 + (strat_ret - bench_ret)
            cum.append(total - 1)
    s = pd.Series(cum)
    s.index = index
    return s


def skewness(prices: Sequence[float]) -> float:
    """Skewness of returns of a price series."""
    p = _to_list(prices)
    if len(p) < 3:
        return 0.0
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    if var == 0:
        return 0.0
    std = sqrt(var)
    m3 = sum((r - mean) ** 3 for r in rets) / len(rets)
    return m3 / (std**3)


def kurtosis(prices: Sequence[float]) -> float:
    """Kurtosis of returns of a price series."""
    p = _to_list(prices)
    if len(p) < 3:
        return 0.0
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    if var == 0:
        return 0.0
    m4 = sum((r - mean) ** 4 for r in rets) / len(rets)
    return m4 / (var**2)


def variance_ratio(prices: Sequence[float], lag: int = 2) -> float:
    """Lo-MacKinlay variance ratio test statistic."""
    p = _to_list(prices)
    if len(p) <= lag:
        return 0.0
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    if var == 0:
        return 0.0
    agg = [sum(rets[i - j] for j in range(1, lag + 1)) for i in range(lag, len(rets))]
    var_lag = sum((a - lag * mean) ** 2 for a in agg) / len(agg)
    return var_lag / (var * lag)


def acf(prices: Sequence[float], lags: Sequence[int]) -> list[float]:
    """Autocorrelation of returns for specified lags."""
    p = _to_list(prices)
    if len(p) < 2:
        return [0.0 for _ in lags]
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    if var == 0:
        return [0.0 for _ in lags]
    out = []
    for lag in lags:
        if lag <= 0 or lag >= len(rets):
            out.append(0.0)
        else:
            cov = sum(
                (rets[i] - mean) * (rets[i - lag] - mean) for i in range(lag, len(rets))
            ) / (len(rets) - lag)
            out.append(cov / var)
    return out


def pacf(prices: Sequence[float], lags: Sequence[int]) -> list[float]:
    """Partial autocorrelation of returns for specified lags."""
    p = _to_list(prices)
    if len(p) < 2:
        return [0.0 for _ in lags]
    rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
    out = []
    for k in lags:
        if k <= 0 or k >= len(rets):
            out.append(0.0)
            continue
        y = [rets[i] for i in range(k, len(rets))]
        X = [[1.0] + [rets[i - j - 1] for j in range(k)] for i in range(k, len(rets))]
        beta = _ols(y, X)
        out.append(beta[-1] if beta else 0.0)
    return out
