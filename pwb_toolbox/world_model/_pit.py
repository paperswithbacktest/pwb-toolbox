"""The point-in-time view of the World Model tables, on pandas frames.

Two clocks, never mixed:

* ``known_at`` -- when the public could know a row. At a knowledge cutoff T,
  a row with ``known_at > T`` does not exist.
* ``[valid_from, valid_to)`` -- when the row is true in the world, half-open,
  ``valid_to`` null when open.

Reading rule of the contract (``docs/world_model/DESIGN.md`` §3.5 in
``data-api``): among the rows with ``known_at <= T``, keep for each key the
row(s) with the latest ``known_at`` -- one publication is a *set* of intervals
-- then keep the one whose interval holds the requested date. A later
publication of a key replaces the earlier one entirely, which is how an
append-only table closes or corrects an interval.

When several ``vintage`` values (generations of the reference tables) carry the
same key with the same ``known_at``, the latest vintage is that publication:
a rebuild re-emits rows, and the newest rebuild is the one to read.
"""

from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

NEW_YORK = "America/New_York"
#: Stand-in for an open interval (``valid_to`` null).
OPEN_END = pd.Timestamp("9999-12-31").as_unit("us")
_DATE_DTYPE = "datetime64[us]"
_KNOWN_DTYPE = "datetime64[us, UTC]"


# --------------------------------------------------------------------------
# Dates and knowledge cutoffs
# --------------------------------------------------------------------------

def as_of_point(as_of) -> tuple[pd.Timestamp, pd.Timestamp]:
    """``(knowledge cutoff in UTC, world date)`` of one ``as_of``.

    * a date, or a naive timestamp at midnight (``"2013-10-01"``,
      ``date(2013, 10, 1)``, a daily bar's index): the whole day is known, up to
      23:59:59.999999 New York time -- the convention the tables use for
      date-only sources;
    * a naive timestamp with a time: that instant, New York time;
    * a timezone-aware timestamp: that instant exactly.

    The world date is the New York calendar date of the cutoff.
    """
    if as_of is None:
        raise ValueError("as_of is required: the World Model is only read point-in-time")
    cutoffs, dates = as_of_points(pd.Series([as_of]))
    return cutoffs.iloc[0], dates.iloc[0]


def as_of_points(values) -> tuple[pd.Series, pd.Series]:
    """Vectorised :func:`as_of_point`: two Series aligned with ``values``."""
    values = pd.Series(values).reset_index(drop=True)
    if values.isna().any():
        raise ValueError("as_of / dates contain a missing value")
    converted = values.map(_as_timestamp)
    cutoffs = pd.Series(pd.NaT, index=values.index, dtype=_KNOWN_DTYPE)
    aware = converted.map(lambda ts: ts.tzinfo is not None)
    if aware.any():
        cutoffs[aware] = pd.DatetimeIndex(
            [ts.tz_convert("UTC") for ts in converted[aware]]
        ).as_unit("us")
    naive = ~aware
    if naive.any():
        local = pd.DatetimeIndex(list(converted[naive])).as_unit("us")
        whole_day = local == local.normalize()
        local = local.where(
            ~whole_day, local + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        )
        cutoffs[naive] = local.tz_localize(NEW_YORK).tz_convert("UTC")
    dates = cutoffs.dt.tz_convert(NEW_YORK).dt.tz_localize(None).dt.normalize()
    return cutoffs, dates.astype(_DATE_DTYPE)


def world_dates(values) -> pd.Series:
    """Calendar dates (naive midnight) of ``values``; a time of day is dropped."""
    values = pd.Series(values).reset_index(drop=True).map(_as_timestamp)
    out = values.map(
        lambda ts: (ts.tz_convert(NEW_YORK).tz_localize(None) if ts.tzinfo else ts).normalize()
    )
    return pd.Series(pd.DatetimeIndex(list(out)).as_unit("us"), dtype=_DATE_DTYPE)


def _as_timestamp(value) -> pd.Timestamp:
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return pd.Timestamp(value.year, value.month, value.day)
    ts = pd.Timestamp(value)
    if ts is pd.NaT:
        raise ValueError(f"not a date: {value!r}")
    return ts


# --------------------------------------------------------------------------
# Identifier values
# --------------------------------------------------------------------------

def normalize_values(values: pd.Series, scheme: str) -> pd.Series:
    """Identifier values as the Identifiers table stores them (§3.2).

    Tickers upper-case, CIKs zero-padded to ten digits; other schemes stripped.
    """
    values = values.astype("string").str.strip()
    if scheme == "ticker_us":
        return values.str.upper()
    if scheme == "cik":
        return values.str.lstrip("0").str.zfill(10)
    return values


# --------------------------------------------------------------------------
# Typing of raw table frames
# --------------------------------------------------------------------------

def typed(frame: pd.DataFrame) -> pd.DataFrame:
    """Fix the dtypes of the temporal columns (dates in µs, ``known_at`` in UTC µs)."""
    frame = frame.copy()
    for column in ("valid_from", "valid_to"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column]).astype(_DATE_DTYPE)
    if "known_at" in frame.columns:
        known = pd.to_datetime(frame["known_at"], utc=True)
        frame["known_at"] = known.astype(_KNOWN_DTYPE)
    return frame


# --------------------------------------------------------------------------
# One as_of: the view
# --------------------------------------------------------------------------

def latest_publication(rows: pd.DataFrame, keys: list[str], cutoff) -> pd.DataFrame:
    """Rows of each key's latest publication with ``known_at <= cutoff``."""
    rows = rows[rows["known_at"] <= cutoff]
    if rows.empty:
        return rows
    latest = rows.groupby(keys, sort=False)["known_at"].transform("max")
    rows = rows[rows["known_at"] == latest]
    if "vintage" in rows.columns:
        top = rows.groupby(keys, sort=False)["vintage"].transform("max")
        rows = rows[rows["vintage"] == top]
    return rows


def latest_period(rows: pd.DataFrame, keys: list[str], cutoff) -> pd.DataFrame:
    """Rows of each key's most recent period known at ``cutoff``, in its latest publication.

    Among the rows with ``known_at <= cutoff``, each key keeps those with the
    largest ``valid_from`` (the reference period), then, within that period,
    the latest publication (``known_at``, then ``vintage``) -- a correction of
    the period replaces it, a correction of an older period does not. The
    interval is not tested against a date: the reader chooses the vintage.
    """
    rows = rows[rows["known_at"] <= cutoff]
    if rows.empty:
        return rows
    newest = rows.groupby(keys, sort=False)["valid_from"].transform("max")
    rows = rows[rows["valid_from"] == newest]
    return latest_publication(rows, keys, cutoff)


def valid_on(rows: pd.DataFrame, date) -> pd.DataFrame:
    """Rows whose half-open interval ``[valid_from, valid_to)`` holds ``date``."""
    end = rows["valid_to"].fillna(OPEN_END)
    return rows[(rows["valid_from"] <= date) & (date < end)]


def view(rows: pd.DataFrame, keys: list[str], cutoff, date) -> pd.DataFrame:
    """The contract's reading rule at one ``(cutoff, date)``."""
    return valid_on(latest_publication(rows, keys, cutoff), date)


# --------------------------------------------------------------------------
# Many (key, date, cutoff) queries at once: the panel
# --------------------------------------------------------------------------

def match(rows: pd.DataFrame, keys: list[str], queries: pd.DataFrame) -> pd.Series:
    """For each query, the position in ``rows`` of the row the view returns.

    ``queries`` holds the ``keys`` columns, ``_cutoff`` (UTC) and ``_date``.
    The result is aligned with ``queries`` (same index); ``-1`` means not
    resolved. ``rows`` must be the output of :func:`prepare`.

    Two backward as-of joins, so the cost is a sort of the rows plus a sort of
    the queries -- never rows x queries:

    1. per key, the latest publication with ``known_at <= _cutoff``;
    2. within that publication, the interval with the latest ``valid_from <=
       _date``; it holds the date if ``_date < valid_to``. Intervals of one
       publication may overlap for one entity (never for two, §3.2), so the
       interval reaching furthest so far (a running maximum of ``valid_to``)
       is checked too.
    """
    result = pd.Series(-1, index=queries.index, dtype="int64")
    if rows.empty or queries.empty:
        return result
    q = queries[keys + ["_cutoff", "_date"]].copy()
    q["_qid"] = np.arange(len(q))
    q["_cutoff"] = q["_cutoff"].astype(_KNOWN_DTYPE)
    q["_date"] = q["_date"].astype(_DATE_DTYPE)

    pubs = rows[keys + ["known_at", "_pub"]].drop_duplicates("_pub").sort_values("known_at", kind="mergesort")
    step1 = pd.merge_asof(
        q.sort_values("_cutoff"), pubs, left_on="_cutoff", right_on="known_at",
        by=keys, direction="backward",
    )
    step1 = step1.dropna(subset=["_pub"])
    if step1.empty:
        return result
    step1["_pub"] = step1["_pub"].astype("int64")
    intervals = rows[["_pub", "valid_from", "_end", "_cover_end", "_cover_row", "_pos"]]
    step2 = pd.merge_asof(
        step1[["_qid", "_pub", "_date"]].sort_values("_date"),
        # stable: among equal ``valid_from`` the last row (largest running
        # ``_cover_end``) is the one the backward join returns
        intervals.sort_values("valid_from", kind="mergesort"),
        left_on="_date", right_on="valid_from", by="_pub", direction="backward",
    )
    step2 = step2.dropna(subset=["_pos"])
    own = step2["_date"] < step2["_end"]
    covered = ~own & (step2["_date"] < step2["_cover_end"])
    position = np.where(own, step2["_pos"], np.where(covered, step2["_cover_row"], -1))
    found = pd.Series(position.astype("int64"), index=step2["_qid"].to_numpy())
    found = found[found >= 0]
    values = result.to_numpy().copy()
    values[found.index.to_numpy()] = found.to_numpy()
    return pd.Series(values, index=queries.index)


def prepare(rows: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Sort the rows once and attach what :func:`match` needs.

    Drops empty intervals (``valid_to == valid_from``), keeps only the latest
    vintage of each ``(key, known_at)`` publication, numbers publications
    (``_pub``) and rows (``_pos``), and carries the running maximum of
    ``valid_to`` within each publication (``_cover_end``) with the row that
    reaches it (``_cover_row``).
    """
    rows = rows.copy()
    rows["_end"] = rows["valid_to"].fillna(OPEN_END).astype(_DATE_DTYPE)
    rows = rows[rows["_end"] > rows["valid_from"]]
    group = keys + ["known_at"]
    if "vintage" in rows.columns and not rows.empty:
        top = rows.groupby(group, sort=False)["vintage"].transform("max")
        rows = rows[rows["vintage"] == top]
    rows = rows.sort_values(group + ["valid_from", "_end"], kind="mergesort").reset_index(drop=True)
    if rows.empty:
        for column in ("_pub", "_pos", "_cover_row"):
            rows[column] = pd.Series(dtype="int64")
        rows["_cover_end"] = rows["_end"]
        return rows
    rows["_pub"] = rows.groupby(group, sort=False).ngroup()
    rows["_pos"] = np.arange(len(rows), dtype="int64")
    rows["_cover_end"] = rows.groupby("_pub", sort=False)["_end"].cummax()
    reaching = rows["_pos"].astype("float64").where(rows["_end"] == rows["_cover_end"])
    rows["_cover_row"] = reaching.groupby(rows["_pub"], sort=False).ffill().astype("int64")
    # Rows sharing a ``valid_from`` share the reach of the last of them, so the
    # join may land on any of them.
    ties = rows.groupby(["_pub", "valid_from"], sort=False)
    rows["_cover_end"] = ties["_cover_end"].transform("last")
    rows["_cover_row"] = ties["_cover_row"].transform("last")
    return rows
