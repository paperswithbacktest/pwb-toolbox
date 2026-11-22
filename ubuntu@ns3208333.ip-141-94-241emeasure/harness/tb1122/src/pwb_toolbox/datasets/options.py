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

The loader never answers an empty frame for a reason it could have named. A
source that serves whole files to range requests is an error
(``RangeNotSupportedError``), with a switch to the Hub, announced by a warning,
when ``HF_ACCESS_TOKEN`` is set. A file list whose names carry no month is
sorted by the ``date`` statistics in each file's footer (one range request per
file). A window outside the table, or chains with no row in it, warn.
"""
from __future__ import annotations

import io
import os
import re
import time
import warnings
from datetime import date, datetime
from typing import Iterable, Optional
from urllib.parse import urlparse

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
# The first request of a file asks for its last 64 KiB by a suffix range: the
# answer's ``Content-Range`` gives the size, and the bytes are the Parquet
# footer pyarrow reads next (its own first read is 64 KiB from the end). One
# request where there were two.
_TAIL_BYTES = 64 * 1024
API_BASE_URL = "https://data.paperswithbacktest.com/v1/datasets"


class RangeNotSupportedError(OSError):
    """The server answered a byte-range request with the whole file."""


def _redact(url: str) -> str:
    """Host and path of ``url``: the API's file URLs carry the caller's key in
    their query string, and an error message is not the place for it."""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}"


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
        self._tail_start = None
        self._tail = b""

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
            self._fetch_tail()
        return self._size

    def _fetch_tail(self) -> None:
        resp = self._get(f"bytes=-{_TAIL_BYTES}")
        match = re.match(r"bytes (\d+)-(\d+)/(\d+)$", resp.headers.get("Content-Range", "").strip())
        if not match:
            resp.close()
            raise RangeNotSupportedError(
                f"{_redact(self.url)}: a range request came back without a usable Content-Range "
                f"({resp.headers.get('Content-Range')!r}); the server does not serve byte ranges"
            )
        data = resp.content
        self._size = int(match.group(3))
        self._tail_start = int(match.group(1))
        self._tail = data
        self.bytes_read += len(data)

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
        end = min(self.pos + n, self.size)
        if self._tail_start is not None and self._tail_start <= self.pos and end <= self._tail_start + len(self._tail):
            data = self._tail[self.pos - self._tail_start:end - self._tail_start]
        else:
            data = self._get(f"bytes={self.pos}-{end - 1}").content
            self.bytes_read += len(data)
        self.pos += len(data)
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
                    raise RangeNotSupportedError(
                        f"{_redact(self.url)}: a range request ({byte_range}) was answered with the whole "
                        "file (HTTP 200); this loader reads option shards by range only and does not "
                        "download whole months (~250 MB each)"
                    )
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and status != 429 and status < 500:
                    raise requests.exceptions.HTTPError(
                        f"{status} on {_redact(self.url)} ({byte_range})", response=exc.response
                    ) from None
                last_exc = exc
            except RangeNotSupportedError:
                raise
            except requests.exceptions.RequestException as exc:
                last_exc = exc
            if attempt < _RANGE_ATTEMPTS - 1:
                time.sleep(_RANGE_BACKOFF_SECONDS * 2**attempt)
        raise last_exc


def _hf_sources(hf_token: str) -> list[tuple[str, str, dict]]:
    """``(file name, url, headers)`` of every Parquet file on the Hub, at the current revision."""
    from huggingface_hub import hf_hub_url
    from huggingface_hub.utils import build_hf_headers

    from . import _hub_snapshot

    sha, files = _hub_snapshot(REPO_ID, hf_token)
    headers = build_hf_headers(token=hf_token)
    return [(f, hf_hub_url(REPO_ID, f, repo_type="dataset", revision=sha), headers)
            for f in files if f.endswith(".parquet")]


def _pwb_sources(pwb_api_key: str) -> list[tuple[str, str, dict]]:
    """``(file name, url, headers)`` from the subscriber API's file list.

    Every listed file is returned, whatever its name: ``_select_shards``
    decides which ones the window needs. Until data-api #59 is deployed the
    API names the files by position (``0.parquet`` … ``148.parquet``) and
    the month is not in the name; filtering on it here returned nothing, and
    the loader an empty frame (2026-11-08).
    """
    # The key goes in a header: a query string ends up in the message of any
    # HTTP error raised below.
    resp = requests.get(f"{API_BASE_URL}/{OPTIONS_DAILY_DATASET}", params={"split": "train"},
                        headers={"pwb-api-key": pwb_api_key}, timeout=30)
    if not resp.ok:
        raise requests.exceptions.HTTPError(
            f"{resp.status_code} listing {OPTIONS_DAILY_DATASET} on the PWB data API: {resp.text[:200]}",
            response=resp,
        )
    urls = resp.json().get("files", [])
    return [(urlparse(u).path.rsplit("/", 1)[-1], u, {}) for u in urls]


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


def _date_span(meta, schema: pa.Schema) -> Optional[tuple[str, str]]:
    """``(first, last)`` session of a file, from its row groups' ``date``
    statistics, as ISO strings; ``None`` when a row group has none."""
    d_col = schema.get_field_index("date")
    if d_col < 0:
        return None
    lo = hi = None
    for g in range(meta.num_row_groups):
        span = _stats(meta, g, d_col)
        if span is None:
            return None
        a, b = str(span[0])[:10], str(span[1])[:10]
        lo = a if lo is None or a < lo else lo
        hi = b if hi is None or b > hi else hi
    return (lo, hi) if lo is not None else None


def _select_shards(sources, start: date, end: date, verbose: bool) -> tuple[list, str]:
    """The files of ``sources`` that can hold a session in ``[start, end]``,
    as ``(label, url, headers, handle)``, oldest first, and the span the
    table covers (for the messages).

    By the month in the file name when the names carry one. When none does —
    the subscriber API lists the files by position until data-api #59 is
    deployed — by the ``date`` statistics in each file's footer: one range
    request per file (149 today), so slower, but never an empty answer that
    only means "the names did not match".
    """
    if not sources:
        raise RuntimeError(f"The source lists no file for {OPTIONS_DAILY_DATASET}.")
    by_name = {name: (url, headers) for name, url, headers in sources}
    if any(_SHARD_RE.search(name) for name in by_name):
        months = sorted(_SHARD_RE.search(n).group(2) for n in by_name if _SHARD_RE.search(n))
        covered = f"{months[0]}..{months[-1]}"
        picked = [(name, *by_name[name], None) for name in shards_for_window(by_name, start, end)]
        return picked, covered

    warnings.warn(
        f"The {len(sources)} files listed for {OPTIONS_DAILY_DATASET} carry no month in their names "
        f"(e.g. {sources[0][0]!r}); reading each file's footer to find the months of the window "
        "(one range request per file). With HF_ACCESS_TOKEN set, use_hf=True skips this step.",
        stacklevel=3,
    )
    picked, spans = [], []
    for name, url, headers in sources:
        handle = _open(url, headers)
        f = pq.ParquetFile(handle)
        span = _date_span(f.metadata, f.schema_arrow)
        if span is not None:
            spans.append(span)
            if span[1] < start.isoformat() or span[0] > end.isoformat():
                continue
        picked.append((f"{name} [{span[0]}..{span[1]}]" if span else name, url, headers, handle))
    picked.sort(key=lambda item: item[0].split("[", 1)[-1])
    covered = f"{min(s[0] for s in spans)}..{max(s[1] for s in spans)}" if spans else "unknown"
    if verbose:
        print(f"[options] footers of {len(sources)} files read: {len(picked)} cover the window")
    return picked, covered


def _sources(use_hf: bool) -> tuple[list, str]:
    """The files to read and where they come from: ``"api"`` or ``"hub"``."""
    pwb_api_key = os.getenv("PWB_API_KEY")
    if pwb_api_key and not use_hf:
        return _pwb_sources(pwb_api_key), "api"
    hf_token = os.getenv("HF_ACCESS_TOKEN")
    if not hf_token:
        raise ValueError("Set PWB_API_KEY or HF_ACCESS_TOKEN to load datasets.")
    return _hf_sources(hf_token), "hub"


def _read_window(sources, names, start_d, end_d, columns, verbose):
    shards, covered = _select_shards(sources, start_d, end_d, verbose)
    tables, fetched = [], 0
    for label, url, headers, handle in shards:
        handle = handle if handle is not None else _open(url, headers)
        table = _read_shard(handle, names, start_d, end_d, columns)
        fetched += getattr(handle, "bytes_read", 0)
        if table is not None and table.num_rows:
            tables.append(table)
    if verbose:
        print(f"[options] {', '.join(names)} {start_d}..{end_d}: {len(shards)} monthly shards, "
              f"{fetched / 1e6:.1f} MB fetched")
    return tables, shards, covered


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

    sources, origin = _sources(use_hf)
    try:
        tables, shards, covered = _read_window(sources, names, start_d, end_d, columns, verbose)
    except RangeNotSupportedError as exc:
        if origin != "api":
            raise
        hf_token = os.getenv("HF_ACCESS_TOKEN")
        if not hf_token:
            raise RangeNotSupportedError(
                f"The PWB data API served a whole file to a byte-range request ({exc}). "
                f"{OPTIONS_DAILY_DATASET} is read by range only, so nothing was loaded. Until the "
                "API serves byte ranges, set HF_ACCESS_TOKEN (once your gated access to "
                f"paperswithbacktest/{OPTIONS_DAILY_DATASET} is approved on the Hub) and the "
                "loader will read from the Hub instead."
            ) from None
        warnings.warn(
            f"The PWB data API does not serve byte ranges yet ({exc}); reading "
            f"{OPTIONS_DAILY_DATASET} from the Hub with HF_ACCESS_TOKEN instead.",
            stacklevel=2,
        )
        tables, shards, covered = _read_window(_hf_sources(hf_token), names, start_d, end_d, columns, verbose)

    if not tables:
        if not shards:
            warnings.warn(f"No file of {OPTIONS_DAILY_DATASET} covers {start_d}..{end_d}; "
                          f"the table covers {covered}.", stacklevel=2)
        else:
            warnings.warn(f"No row for {', '.join(names)} between {start_d} and {end_d} in "
                          f"{len(shards)} files of {OPTIONS_DAILY_DATASET}: check the spelling "
                          "(the underlying as named at the time, e.g. FB before June 2022).",
                          stacklevel=2)
        cols = list(KEY_COLUMNS) + [c for c in (columns or []) if c not in KEY_COLUMNS]
        return pd.DataFrame(columns=cols)
    df = pa.concat_tables(tables, promote_options="default").to_pandas()
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    df["symbol"] = df["symbol"].astype(object)
    return df.sort_values(["underlying", "date", "symbol"], kind="stable").reset_index(drop=True)
