from calendar import month_abbr
from typing import Sequence

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
