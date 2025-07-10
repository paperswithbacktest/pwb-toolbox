from calendar import month_abbr
from typing import Sequence, Tuple
from math import sqrt
from statistics import NormalDist

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


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


def returns_table(prices: 'pd.Series') -> 'pd.DataFrame':  # type: ignore
    """Return monthly and yearly percentage returns from a daily price series."""
    if pd is None:
        raise ImportError("pandas is required for returns_table")

    price_list = _to_list(prices)
    index = list(getattr(prices, 'index', range(len(price_list))))

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


def rolling_cumulative_return(prices: 'pd.Series', window: int) -> 'pd.Series':  # type: ignore
    """Rolling cumulative return over a specified window."""
    if pd is None:
        raise ImportError("pandas is required for rolling_cumulative_return")

    p = _to_list(prices)
    index = list(getattr(prices, 'index', range(len(p))))
    out = []
    for i in range(len(p)):
        if i < window:
            out.append(None)
        else:
            out.append(p[i] / p[i - window] - 1)
    s = pd.Series(out)
    s.index = index
    return s


def annualized_volatility(prices: Sequence[float], periods_per_year: int = 252) -> float:
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
        sum_sq += dd ** 2
    return sqrt(sum_sq / len(p))


def ulcer_performance_index(prices: Sequence[float], risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
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


def parametric_expected_shortfall(prices: Sequence[float], level: float = 0.05) -> float:
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
