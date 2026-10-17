"""The point-in-time universe of large, liquid US equities.

``SP500_SYMBOLS`` is 503 symbols frozen at *today's* index composition and
replayed back to 1990, and ``backtesting.universe.get_most_liquid_symbols``
ranks liquidity on the **last** bar and replays that ranking over the whole
history. Both are look-ahead: a backtest that starts in 2003 holds the winners
of 2026, and never holds the names that mattered then and died since.

This module replaces both. At each session it asks which names were actually
trading and how much, and keeps the largest by median dollar volume over the
preceding 60 sessions. Two depths are exposed as pseudo-symbols: ``"sp500"``
cuts at rank 500; ``"liquid1000"`` at rank 1000, the full depth of the
published table, with a twelve-month point-in-time tenure floor (see
:func:`load_pit_universe`) so a backtest does not carry a feed for every
brief visitor.

Why liquidity and not index membership: the vendor serves no historical index
constituents (every candidate endpoint 404s), so "the S&P 500 as of 2010" is not
recoverable from the data we have. A point-in-time liquidity screen is, and it
is what the academic literature uses for "large, liquid US equities".

Why the median over 60 sessions rather than the day's volume: one exceptional
session -- an earnings release, an index add, a short squeeze -- should not pull
a name into the universe for a single day and out again the next.

The table is built by ``data-api``'s ``pit_liquid_universe`` job from the daily
consolidated aggregates; see that module for the three traps it has to avoid
(the ``type`` field is empty for AAPL and MSFT before ~2015, exchange test
tickers such as ``ZVZZT`` trade in size, and the rolling median needs a wider
pre-ranking than the published cut).
"""

import os

import pandas as pd

DATASET = "Stocks-Daily-LiquidUniverse"

# A session's membership also covers the days that follow it until the next
# session: a quarterly fundamentals row stamped on a Saturday, or on a market
# holiday, must still resolve. Seven calendar days clears any weekend plus
# holiday run. Beyond that the name has genuinely left the universe, and a
# backward as-of join must not resurrect it -- which is exactly what an
# untolerated join would do for a name that dropped out years earlier.
_ASOF_TOLERANCE = pd.Timedelta(days=7)

# Set this to a directory of per-year parquet files to read the table from disk
# instead of the Hub -- what the build job writes, and what lets the correction
# be tested before the dataset is published.
_LOCAL_DIR_ENV = "PWB_PIT_UNIVERSE_DIR"

_cache = {}


def load_pit_universe(top_n: int = 500, min_months: int = 0) -> pd.DataFrame:
    """The ``(date, symbol, rank)`` membership table, ranks 1..``top_n``.

    ``min_months`` is a **point-in-time tenure** floor: a name only counts as
    a member once it has spent that many calendar months in the top ``top_n``,
    counted up to the date in question and never beyond it. It exists to cut
    the number of price feeds a backtest carries: every name that ever passed
    through the universe needs one, backtrader pays for each at every bar, and
    the brief visitors are the majority -- of the 3,954 names ever in the top
    1000, 1,280 spent less than a year there. Measured with ``min_months=12``:
    2,674 feeds instead of 3,954, and still 840 names per session in 2004, the
    first full year of the table. A longer floor empties the early years
    (24 months loses 2004, 36 loses 2005-2006), because the table starts in
    October 2003 and tenure cannot be known before it.

    Cached per ``(top_n, min_months)``: a campaign runs thousands of backtests
    in one process and the table is the same for all of them.
    """
    key = (top_n, min_months)
    if key in _cache:
        return _cache[key]

    local = os.getenv(_LOCAL_DIR_ENV)
    if local:
        import glob

        files = sorted(glob.glob(os.path.join(local, "*.parquet")))
        if not files:
            raise FileNotFoundError(
                f"{_LOCAL_DIR_ENV}={local} holds no .parquet file. It should "
                "point at the per-year output of the pit_liquid_universe job."
            )
        df = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    else:
        from . import load_dataset  # late: load_dataset lives in the package __init__

        try:
            df = load_dataset(DATASET)
        except Exception as exc:
            # Say which dataset and which escape hatch, rather than let a Hub
            # 404 surface as-is: ``"sp500"`` is reached by 1 217 strategies and
            # the failure has to name its own cause.
            raise RuntimeError(
                f"the point-in-time universe {DATASET!r} could not be loaded "
                f"({type(exc).__name__}: {exc}). Publish it, or point "
                f"{_LOCAL_DIR_ENV} at a local build of it. Until then, "
                '"sp500-frozen" gives the old frozen-composition behaviour -- '
                "which carries the look-ahead this table exists to remove."
            ) from exc

    df = df[df["rank"] <= top_n].copy()
    df["date"] = pd.to_datetime(df["date"])
    if min_months:
        df = _with_tenure(df)
        df = df[df["tenure"] >= min_months].drop(columns=["tenure"])
    df = df.sort_values(["date", "rank"])[["date", "symbol", "rank"]]
    _cache[key] = df
    return df


def _with_tenure(df: pd.DataFrame) -> pd.DataFrame:
    """Attach each row's point-in-time tenure: months in the universe so far, this one included."""
    out = df.assign(month=df["date"].dt.to_period("M"))
    tenure = out[["symbol", "month"]].drop_duplicates().sort_values(["symbol", "month"])
    tenure["tenure"] = tenure.groupby("symbol").cumcount() + 1
    out = out.merge(tenure, on=["symbol", "month"], how="left")
    return out.drop(columns=["month"])


def pit_symbols(top_n: int = 500, min_months: int = 0) -> list:
    """Every symbol that was in the universe at any point.

    This is what has to be *loaded*: a backtest spanning 2003-2026 needs the
    price history of all 2 013 names that passed through the top 500, not just
    the 500 holding it today. Membership is then enforced per date by
    :func:`apply_pit_membership`, so the extra names cost loading time but never
    enter a position outside their own window.
    """
    return sorted(load_pit_universe(top_n, min_months)["symbol"].unique().tolist())


def apply_pit_membership(df: pd.DataFrame, top_n: int = 500, min_months: int = 0) -> pd.DataFrame:
    """Drop every row whose symbol was not in the universe on its own date.

    Rows are dropped rather than masked: in the long format every consumer
    already tolerates a symbol being absent on a date, and a pivot turns the
    gap into the ``NaN`` that a cross-sectional sort skips on its own. Masking
    the price columns instead would leave a row that a ``ffill`` could revive.

    Matching is a backward as-of join on the date, so a row stamped between
    sessions resolves to the last session's membership -- which makes this
    correct for quarterly fundamentals as well as for daily prices.
    """
    if "symbol" not in df.columns or "date" not in df.columns or df.empty:
        return df

    universe = load_pit_universe(top_n, min_months)

    out = df.copy()
    original_dtype = out["date"].dtype
    out["date"] = pd.to_datetime(out["date"])
    # merge_asof requires both sides sorted on the join key, and `by` groups
    # must not be dropped, so sort rather than assume.
    out = out.sort_values("date", kind="stable")
    order = out.index
    out = out.reset_index(drop=True)

    # merge_asof refuses to join an ``object`` key against a ``string[python]``
    # one, and which of the two a ``symbol`` column carries depends on where it
    # was read from -- parquet gives the arrow-backed dtype, the Hub loaders
    # give plain objects. Normalise both sides rather than depend on the source.
    left = out[["date", "symbol"]].copy()
    left["symbol"] = left["symbol"].astype(str)
    right = universe.rename(columns={"rank": "_pit_rank"}).copy()
    right["symbol"] = right["symbol"].astype(str)

    matched = pd.merge_asof(
        left,
        right,
        on="date",
        by="symbol",
        direction="backward",
        tolerance=_ASOF_TOLERANCE,
    )
    keep = matched["_pit_rank"].notna().to_numpy()
    out = out[keep]

    # restore the caller's row order and date dtype, so the filter is invisible
    # apart from the rows it removed
    out = out.set_index(order[keep]).sort_index()
    if original_dtype == object:
        out["date"] = out["date"].dt.date
    return out
