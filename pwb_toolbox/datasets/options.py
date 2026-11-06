"""Bounded reads of ``Options-Daily-Price``: one or a few option chains over a date window.

The table holds every US-listed option contract that traded, one row per
contract and session since 2014-06: about 560 million rows, ~20 GB in monthly
shards. ``load_dataset`` downloads every shard of a dataset before filtering,
which is how ``Stocks-1Min-Price`` filled a 460 GB disk on 2026-11-05. This
loader never does that:

1. **Underlyings are required, and so is the window.** ``underlyings=None``
   and an open-ended window are refused, not defaulted.
2. **Dates are filtered before anything is downloaded.** The shards are
   monthly (``data/train-YYYY-MM.parquet``); only the months that intersect
   ``[start, end]`` are opened at all.
3. **Inside a month, only the chain's row groups are fetched.** The shards are
   sorted by ``underlying`` then ``date`` in 100k-row row groups, so the
   min/max statistics of ``underlying`` single out the row groups of a chain.
   Each shard is read over HTTP range requests: the footer, then the selected
   row groups of the selected columns. October 2026: SPY is 2 row groups and
   7.7 MB, AAPL 1 and 3.6 MB, against 274 MB for the whole month.
4. **Columns are chosen by the caller** (``columns=``), on top of the three
   keys ``symbol``, ``date``, ``underlying``.

Example::

    from pwb_toolbox.datasets import load_option_chain

    chain = load_option_chain(["SPY"], "2024-01-01", "2024-03-31",
                              columns=["expiration", "strike", "option_type", "close",
                                       "volume", "implied_volatility", "delta"])

Access is the same as ``load_dataset``: ``PWB_API_KEY`` (the subscriber API
hands out one URL per shard) or ``HF_ACCESS_TOKEN`` (the Hub, after the gated
request is approved).
"""
from __future__ import annotations

import io
import os
import re
import time
from datetime import date, datetime
from typing import Iterable, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import requests

OPTIONS_DAILY_DATASET = "Options-Daily-Price"
REPO_ID = f"paperswithbacktest/{OPTIONS_DAILY_DATASET}"
KEY_COLUMNS = ("symbol", "date", "underlying")
DATE_COLUMNS = ("date", "expiration")

_SHARD_RE = re.compile(r"(^|/)train-(\d{4}-\d{2})\.parquet$")
_RANGE_ATTEMPTS = 4
_RANGE_BACKOFF_SECONDS = 2.0
_RANGE_TIMEOUT_SECONDS = 120


# --------------------------------------------------------------------------- #
# Arguments                                                                   #
# --------------------------------------------------------------------------- #
def _as_date(value, name: str) -> date:
    if value is None:
        raise ValueError(f"{name} is required: the option table is too large to read without a window")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name}={value!r} is not a date") from exc


def _as_underlyings(underlyings) -> list[str]:
    if isinstance(underlyings, str):
        underlyings = [underlyings]
    if underlyings is None:
        raise ValueError("underlyings is required: name the chains to load, e.g. ['SPY']")
    names = sorted({str(u).strip().upper() for u in underlyings if str(u).strip()})
    if not names:
        raise ValueError("underlyings is empty: name the chains to load, e.g. ['SPY']")
    return names


def months_between(start: date, end: date) -> list[str]:
    """``YYYY-MM`` of every month that intersects ``[start, end]``."""
    return [p.strftime("%Y-%m") for p in pd.period_range(start, end, freq="M")]


def shards_for_window(files: Iterable[str], start: date, end: date) -> list[str]:
    """The shard names among ``files`` whose month intersects the window, oldest first."""
    wanted = set(months_between(start, end))
    picked = []
    for name in files:
        m = _SHARD_RE.search(name)
        if m and m.group(2) in wanted:
            picked.append((m.group(2), name))
    return [name for _, name in sorted(picked)]


# --------------------------------------------------------------------------- #
# Range reads                                                                 #
# --------------------------------------------------------------------------- #
class RangeFile(io.RawIOBase):
    """A read-only, seekable file over HTTP range requests.

    Enough of the file protocol for ``pyarrow.parquet.ParquetFile``: it reads
    the footer from the end, then the byte ranges of the row groups and
    columns it is asked for, and nothing else. ``bytes_read`` counts what came
    over the wire.
    """

    def __init__(self, url: str, headers: Optional[dict] = None, session: Optional[requests.Session] = None):
        super().__init__()
        self.url = url
        self.headers = dict(headers or {})
        self.session = session or requests.Session()
        self.pos = 0
        self.bytes_read = 0
        self.requests = 0
        self._size = None

    # -- protocol ----------------------------------------------------------
    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    @property
    def size(self) -> int:
        if self._size is None:
            resp = self._get("bytes=0-0")
            total = resp.headers.get("Content-Range", "").rsplit("/", 1)[-1]
            if not total.isdigit():
                raise OSError(f"{self.url}: the server does not answer range requests")
            self._size = int(total)
        return self._size

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        else:
            raise ValueError(f"bad whence {whence}")
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        data = self._get(f"bytes={self.pos}-{end}").content
        self.pos += len(data)
        self.bytes_read += len(data)
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    # -- transport ---------------------------------------------------------
    def _get(self, byte_range: str) -> requests.Response:
        last_exc = None
        for attempt in range(_RANGE_ATTEMPTS):
            try:
                self.requests += 1
                # Streamed, so a server that ignores Range is refused before
                # its body (a whole shard, ~250 MB) is read into memory.
                resp = self.session.get(self.url, headers={**self.headers, "Range": byte_range},
                                        timeout=_RANGE_TIMEOUT_SECONDS, stream=True)
                if resp.status_code == 200:
                    resp.close()
                    raise OSError(f"{self.url}: range request answered with the whole file")
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and status != 429 and status < 500:
                    raise
                last_exc = exc
            except requests.exceptions.RequestException as exc:
                last_exc = exc
            if attempt < _RANGE_ATTEMPTS - 1:
                time.sleep(_RANGE_BACKOFF_SECONDS * 2**attempt)
        raise last_exc


def _hf_sources(hf_token: str) -> list[tuple[str, str, dict]]:
    """``(shard name, url, headers)`` of every shard on the Hub, at the current revision."""
    from huggingface_hub import hf_hub_url
    from huggingface_hub.utils import build_hf_headers

    from . import _hub_snapshot

    sha, files = _hub_snapshot(REPO_ID, hf_token)
    headers = build_hf_headers(token=hf_token)
    return [(f, hf_hub_url(REPO_ID, f, repo_type="dataset", revision=sha), headers)
            for f in files if _SHARD_RE.search(f)]


def _pwb_sources(pwb_api_key: str) -> list[tuple[str, str, dict]]:
    """``(shard name, url, headers)`` from the subscriber API's file list."""
    resp = requests.get(f"https://data.paperswithbacktest.com/v1/datasets/{OPTIONS_DAILY_DATASET}",
                        params={"pwb_api_key": pwb_api_key, "split": "train"}, timeout=30)
    resp.raise_for_status()
    urls = resp.json().get("files", [])
    return [(u.split("?", 1)[0].rsplit("/", 1)[-1], u, {}) for u in urls if _SHARD_RE.search(u.split("?", 1)[0])]


def _open(url: str, headers: dict):
    """The file object a shard is read through (replaced in tests)."""
    return RangeFile(url, headers)


# --------------------------------------------------------------------------- #
# Row-group selection                                                         #
# --------------------------------------------------------------------------- #
def _stats(meta, group: int, column: int):
    s = meta.row_group(group).column(column).statistics
    if s is None or not s.has_min_max:
        return None
    lo, hi = s.min, s.max
    if isinstance(lo, bytes):
        lo, hi = lo.decode(), hi.decode()
    return lo, hi


def select_row_groups(meta, schema: pa.Schema, underlyings: list[str], start: date, end: date) -> list[int]:
    """Row groups whose ``underlying`` and ``date`` ranges can hold a wanted row.

    A row group without statistics is kept (read and filtered), never dropped.
    """
    u_col = schema.get_field_index("underlying")
    d_col = schema.get_field_index("date")
    lo_d, hi_d = start.isoformat(), end.isoformat()
    picked = []
    for g in range(meta.num_row_groups):
        u = _stats(meta, g, u_col)
        if u is not None and not any(u[0] <= name <= u[1] for name in underlyings):
            continue
        d = _stats(meta, g, d_col)
        if d is not None and (d[1] < lo_d or d[0] > hi_d):
            continue
        picked.append(g)
    return picked


def _read_shard(source, underlyings: list[str], start: date, end: date, columns: Optional[list[str]]):
    f = pq.ParquetFile(source)
    schema = f.schema_arrow
    if columns is None:
        cols = schema.names
    else:
        unknown = sorted(set(columns) - set(schema.names))
        if unknown:
            raise ValueError(f"unknown columns {unknown}; the table has {schema.names}")
        cols = list(dict.fromkeys(list(KEY_COLUMNS) + list(columns)))
    groups = select_row_groups(f.metadata, schema, underlyings, start, end)
    if not groups:
        return None
    table = f.read_row_groups(groups, columns=cols)
    keep = pc.and_(
        pc.is_in(table.column("underlying"), value_set=pa.array(underlyings, pa.string())),
        pc.and_(pc.greater_equal(table.column("date"), start.isoformat()),
                pc.less_equal(table.column("date"), end.isoformat())),
    )
    return table.filter(keep)


def load_option_chain(underlyings, start, end, columns=None, use_hf: bool = False,
                      verbose: bool = True) -> pd.DataFrame:
    """Daily bars of the option contracts of ``underlyings`` between ``start`` and ``end``.

    Parameters
    ----------
    underlyings : str or list of str, required
        Underlying tickers as the table spells them (``"SPY"``, ``"SPX"``,
        ``"AAPL"``; the name at the time, so ``"FB"`` before June 2022).
    start, end : date-like, required
        Inclusive window on the session date.
    columns : list of str, optional
        Columns to download besides ``symbol``, ``date`` and ``underlying``.
        Default: all of them. Fewer columns, fewer bytes.
    use_hf : bool
        Read from the Hub even when ``PWB_API_KEY`` is set.

    Returns
    -------
    pandas.DataFrame, one row per contract and session, sorted by underlying,
    date and symbol, ``date`` and ``expiration`` as ``datetime.date``.
    """
    names = _as_underlyings(underlyings)
    start_d, end_d = _as_date(start, "start"), _as_date(end, "end")
    if start_d > end_d:
        raise ValueError(f"start {start_d} is after end {end_d}")

    pwb_api_key = os.getenv("PWB_API_KEY")
    if pwb_api_key and not use_hf:
        sources = _pwb_sources(pwb_api_key)
    else:
        hf_token = os.getenv("HF_ACCESS_TOKEN")
        if not hf_token:
            raise ValueError("Set PWB_API_KEY or HF_ACCESS_TOKEN to load datasets.")
        sources = _hf_sources(hf_token)

    by_name = {name: (url, headers) for name, url, headers in sources}
    shards = shards_for_window(by_name, start_d, end_d)
    tables, fetched = [], 0
    for shard in shards:
        url, headers = by_name[shard]
        handle = _open(url, headers)
        table = _read_shard(handle, names, start_d, end_d, columns)
        fetched += getattr(handle, "bytes_read", 0)
        if table is not None and table.num_rows:
            tables.append(table)
    if verbose:
        print(f"[options] {', '.join(names)} {start_d}..{end_d}: {len(shards)} monthly shards, "
              f"{fetched / 1e6:.1f} MB fetched")
    if not tables:
        cols = list(KEY_COLUMNS) + [c for c in (columns or []) if c not in KEY_COLUMNS]
        return pd.DataFrame(columns=cols)
    df = pa.concat_tables(tables, promote_options="default").to_pandas()
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    df["symbol"] = df["symbol"].astype(object)
    return df.sort_values(["underlying", "date", "symbol"], kind="stable").reset_index(drop=True)
