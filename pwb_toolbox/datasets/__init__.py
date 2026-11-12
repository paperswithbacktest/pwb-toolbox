from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from io import BytesIO
import os
import re
import tempfile
import threading
import time
from urllib.parse import parse_qsl, urlparse
import warnings

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.constants import HF_HUB_CACHE
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from tqdm import tqdm


def _get_hf_token() -> str:
    token = os.getenv("HF_ACCESS_TOKEN")
    if not token:
        raise ValueError("HF_ACCESS_TOKEN not set")
    return token


def _get_pwb_api_key() -> str | None:
    return os.getenv("PWB_API_KEY")


def _symbols_overlap(cell, symbol_set) -> bool:
    """True if a news-style ``symbols`` list cell shares any ticker with ``symbol_set``."""
    if cell is None:
        return False
    return any(symbol in symbol_set for symbol in cell)


def _read_one_parquet(source, symbols=None, columns=None, window=None) -> pd.DataFrame:
    """Read a single parquet source, pushing the symbol filter down when possible.

    ``source`` is a local path (``str``) or a file-like object. When ``symbols``
    is provided, the scalar ``symbol`` column is filtered via parquet predicate
    pushdown (which prunes row groups, so a whole shard is never materialised),
    and the news-style list column ``symbols`` is filtered row-wise right after
    the read. Either way memory stays bounded to a single shard's matching rows
    instead of the full dataset, which is what makes large sharded datasets
    (e.g. the 75 GB 1-minute prices) loadable when a symbol subset is requested.

    ``columns`` (a list) projects the read onto those columns plus the keys
    (``symbol``, ``symbols``, ``date``, ``datetime``) the shard has, and
    ``window`` (a ``_Window``) filters the ``datetime`` column, or the ``date``
    column when there is none, in the same pushed-down read. Arrow filters the
    rows before pandas sees them, so only matching rows of the selected
    columns are ever converted.
    """
    filters = []
    read_columns = None
    if symbols or columns is not None or window is not None:
        schema = pq.read_schema(source)
        if hasattr(source, "seek"):
            source.seek(0)
        if symbols and "symbol" in schema.names:
            filters.append(("symbol", "in", list(symbols)))
        if window is not None:
            filters.extend(window.filters(schema))
        if columns is not None:
            read_columns = _projection(schema, columns)

    df = pd.read_parquet(source, filters=filters or None, columns=read_columns)

    if symbols and "symbol" not in df.columns and "symbols" in df.columns:
        symbol_set = set(symbols)
        df = df[df["symbols"].apply(lambda cell: _symbols_overlap(cell, symbol_set))]

    return _normalise_symbol(df)


#: Columns every bounded read keeps, whatever ``columns=`` asks for: without
#: them the rows cannot be told apart or placed in time.
_KEY_COLUMNS = ("symbol", "symbols", "date", "datetime")


def _projection(schema, columns) -> list[str]:
    """The keys the shard has, then ``columns``, in order and without repeats."""
    unknown = [c for c in columns if c not in schema.names]
    if unknown:
        raise ValueError(f"unknown columns {unknown}; the dataset has {list(schema.names)}")
    keys = [c for c in _KEY_COLUMNS if c in schema.names]
    return list(dict.fromkeys(keys + list(columns)))


class _Window:
    """An inclusive window on a dataset's time column, from ``start``/``end``.

    A bound given as a bare date covers the whole day: ``end="2024-03-31"``
    keeps every bar of 31 March. A bound with a time of day is taken as is and
    compared with the stored timestamps, which are naive (no time zone) in
    every PWB table.
    """

    def __init__(self, start=None, end=None, rows=True):
        # ``rows=False``: the window only picks the shards to read, and every
        # row of those shards is kept. What ``get_pricing`` uses, since it
        # slices the dates itself afterwards (see ``_pricing_shard_window``).
        self.rows = rows
        self.lo = self._timestamp(start, "start")
        hi = self._timestamp(end, "end")
        # A bare-date end becomes an exclusive bound at the next midnight.
        self.hi_exclusive = hi is not None and hi == hi.normalize()
        self.hi = hi + pd.Timedelta(days=1) if self.hi_exclusive else hi
        if self.lo is not None and self.hi is not None:
            if self.lo >= self.hi if self.hi_exclusive else self.lo > self.hi:
                raise ValueError(f"start {start} is after end {end}")

    @staticmethod
    def _timestamp(value, name):
        if value is None:
            return None
        try:
            ts = pd.Timestamp(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{name}={value!r} is not a date") from exc
        if ts.tzinfo is not None:
            raise ValueError(
                f"{name}={value!r} carries a time zone; PWB timestamps are stored naive, "
                "pass the bound as it is written in the table"
            )
        return ts

    def key(self):
        """Hashable identity of the row filter, for the read memo."""
        return (self.lo, self.hi, self.hi_exclusive)

    def __repr__(self):
        lo = "..." if self.lo is None else str(self.lo)
        hi = "..." if self.hi is None else str(self.hi)
        return f"[{lo}, {hi}{')' if self.hi_exclusive else ']'}"

    def describe(self) -> str:
        lo = "start" if self.lo is None else self.lo.strftime("%Y-%m-%d")
        if self.hi is None:
            hi = "end"
        else:
            last = self.hi - pd.Timedelta(days=1) if self.hi_exclusive else self.hi
            hi = last.strftime("%Y-%m-%d")
        return f"{lo}..{hi}"

    # -- shard selection ---------------------------------------------------
    def overlaps(self, period_start: pd.Timestamp, period_end: pd.Timestamp) -> bool:
        """True if a shard holding ``[period_start, period_end)`` can hold a
        row of the window.

        One day of slack on each side: a shard is named after the period of
        its source, and its timestamps can be shifted by a time-zone
        conversion (``Cryptocurrencies-1Min-Price``'s June shard opens on
        ``2023-05-31 20:00:00``). Rows outside the window are filtered on read.
        """
        slack = pd.Timedelta(days=1)
        if self.lo is not None and period_end + slack <= self.lo:
            return False
        if self.hi is not None and period_start - slack > self.hi:
            return False
        return True

    # -- row filter --------------------------------------------------------
    def filters(self, schema) -> list[tuple]:
        """Parquet filters for this window on ``schema``'s time column."""
        if "datetime" in schema.names:
            field = schema.field("datetime")
        elif "date" in schema.names:
            field = schema.field("date")
        else:
            raise ValueError(
                f"start/end need a 'datetime' or 'date' column; the dataset has {list(schema.names)}"
            )
        lo, hi, hi_exclusive = self.lo, self.hi, self.hi_exclusive
        kind = field.type
        daily = field.name == "date" or pa.types.is_date(kind)
        if daily:
            # Day granularity: a bound with a time of day keeps its whole day.
            lo = None if lo is None else lo.normalize()
            if hi is not None and not hi_exclusive:
                hi, hi_exclusive = hi.normalize() + pd.Timedelta(days=1), True

        if pa.types.is_string(kind) or pa.types.is_large_string(kind):
            # ISO strings sort as the instants they spell. A midnight bound is
            # written as a bare date, so it compares right whether the table
            # separates date and time with a space or with "T".
            def fmt(ts):
                return ts.strftime("%Y-%m-%d") if ts == ts.normalize() else ts.strftime("%Y-%m-%d %H:%M:%S")
        elif pa.types.is_date(kind):
            def fmt(ts):
                return ts.date()
        elif pa.types.is_timestamp(kind):
            def fmt(ts):
                return ts.tz_localize(kind.tz) if kind.tz else ts
        else:
            raise ValueError(f"start/end cannot filter column {field.name!r} of type {kind}")

        out = []
        if lo is not None:
            out.append((field.name, ">=", fmt(lo)))
        if hi is not None:
            out.append((field.name, "<" if hi_exclusive else "<=", fmt(hi)))
        return out


def _normalise_symbol(df: pd.DataFrame) -> pd.DataFrame:
    """``symbol`` as plain ``object`` strings, and no row without one.

    The contract of every PWB feed has been an ``object`` symbol column, and
    strategies lean on it: 106 published ones merge the stock feed on
    ``symbol`` against a fundamentals frame, others loop over
    ``df["symbol"].unique()``. A shard written with pandas metadata hands back
    ``string[python]`` instead, and that is enough to kill both patterns --
    ``pd.merge_asof`` refuses "incompatible merge keys string[python] and
    object", and ``"-" in s`` raises on a ``pd.NA`` symbol. Measured on the
    2026-10-19 campaign: two published strategies died exactly that way after
    ``Stocks-Daily-Price`` was rebuilt as monthly shards on 2026-10-11.

    The feed is fixed upstream, but a reader must not depend on how a shard
    was written. A row without a symbol is unusable and is dropped.
    """
    if "symbol" not in df.columns:
        return df
    symbol = df["symbol"]
    if symbol.dtype != object or symbol.isna().any():
        keep = symbol.notna()
        if not keep.all():
            df = df[keep]
        df = df.copy()
        df["symbol"] = df["symbol"].astype(object)
    return df


# A dataset read through the subscriber API is one GET per shard, 778 of them for
# ``Stocks-Daily-Price``, and the Hub path caches nothing across them. Measured
# 2026-10-18: a single ``SSL: UNEXPECTED_EOF_WHILE_READING`` on shard 645 lost the
# thirteen minutes before it. One dropped connection in several hundred is the
# normal case for a transfer that long, so a shard is retried before the read
# fails, with a pause that doubles each time.
_HTTP_ATTEMPTS = 4
_HTTP_BACKOFF_SECONDS = 2.0
_HTTP_TIMEOUT_SECONDS = 120


def _http_get(url: str) -> bytes:
    """The body at ``url``, retrying transient transport and server errors.

    Retried: any ``requests`` transport failure (reset, SSL EOF, timeout,
    truncated body) and a 5xx or 429 answer. Not retried: a 4xx other than
    429, which says the request itself is wrong -- a bad key or a missing
    shard -- and will not improve with waiting.
    """
    last_exc = None
    for attempt in range(_HTTP_ATTEMPTS):
        try:
            resp = requests.get(url, timeout=_HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.content
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status != 429 and status < 500:
                raise
            last_exc = exc
        except requests.exceptions.RequestException as exc:
            last_exc = exc
        if attempt < _HTTP_ATTEMPTS - 1:
            time.sleep(_HTTP_BACKOFF_SECONDS * 2**attempt)
    raise last_exc


# --------------------------------------------------------------------------- #
# In-process memo of the shard reads                                          #
# --------------------------------------------------------------------------- #
# A backtest reads the same shards several times in one process. Measured on
# 0.1.49 (12 Nov 2026) for a ``sp500`` point-in-time strategy: the 779 monthly
# shards of ``Stocks-Daily-Price`` were read by ``get_pricing`` (14 s), again by
# the Roll fallback of the cost schedules (4 s), and again by the strategy's own
# ``load_dataset("Stocks-Daily-Price", symbols=["sp500"])`` (18-23 s).
#
# The memo keeps each shard as it came out of ``_read_one_parquet``, keyed by
# the file on disk (path, size, modification time, inode -- a new Hub revision
# is a new snapshot path, a new API download a new blob) and by the filters of
# the read (symbols as a set, columns, row window). The same key is the same
# bytes read with the same filters, so the same frame. A caller never receives
# the stored object: several shards are concatenated into a new frame, a single
# one is copied.
#
# It is bounded (``PWB_READ_MEMO_MB``, default 2048; 0 turns it off). A shard is
# admitted only if it fits once the entries of earlier reads are evicted, least
# recently used first, so a read larger than the budget keeps what it could
# store instead of evicting its own first shards to admit its last ones.
_READ_MEMO_DEFAULT_MB = 2048


def _read_memo_budget() -> int:
    try:
        mb = float(os.getenv("PWB_READ_MEMO_MB", _READ_MEMO_DEFAULT_MB))
    except ValueError:
        mb = _READ_MEMO_DEFAULT_MB
    return int(max(mb, 0) * 1024 * 1024)


def _frame_bytes(df: pd.DataFrame) -> int:
    """Rough size of a frame: its arrays, plus a pointer and a share of a
    string object per object cell (pyarrow deduplicates the strings it
    converts, so ``deep=True`` would mostly count the same objects again)."""
    shallow = int(df.memory_usage(index=True, deep=False).sum())
    objects = sum(len(df) for dtype in df.dtypes if dtype == object)
    return shallow + 24 * objects


class _ReadMemo:
    def __init__(self):
        self._entries = OrderedDict()  # key -> [frame, nbytes, generation]
        self._by_file = defaultdict(set)  # (file, columns, window) -> {key}
        self._lock = threading.Lock()
        self.nbytes = 0
        self.generation = 0
        self.hits = 0
        self.misses = 0

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._by_file.clear()
            self.nbytes = 0
            self.hits = self.misses = 0

    def next_generation(self) -> int:
        with self._lock:
            self.generation += 1
            return self.generation

    def get(self, key, generation):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            entry[2] = generation
            self._entries.move_to_end(key)
            self.hits += 1
            return entry[0]

    def get_superset(self, key, generation):
        """A stored read of the same file whose symbols include ``key``'s.

        Returns ``(frame, wanted symbols)`` or ``None``. Only for a read with
        a symbol set and a scalar ``symbol`` column; see ``superset_reads``.
        """
        ident, wanted, columns, window = key
        if not wanted:
            return None
        with self._lock:
            for other in self._by_file.get((ident, columns, window), ()):
                have = other[1]
                if have is not None and not wanted <= have:
                    continue
                entry = self._entries[other]
                if "symbol" not in entry[0].columns:
                    continue
                entry[2] = generation
                self._entries.move_to_end(other)
                self.hits += 1
                return entry[0], wanted
        return None

    def put(self, key, frame, generation, budget):
        size = _frame_bytes(frame)
        with self._lock:
            if key in self._entries or size > budget:
                return
            for old in list(self._entries):
                if self.nbytes + size <= budget:
                    break
                if self._entries[old][2] >= generation:
                    continue  # read by the current call: never evicted for it
                self._drop(old)
            if self.nbytes + size > budget:
                return
            self._entries[key] = [frame, size, generation]
            self._by_file[(key[0], key[2], key[3])].add(key)
            self.nbytes += size

    def _drop(self, key):
        frame, size, _ = self._entries.pop(key)
        group = self._by_file.get((key[0], key[2], key[3]))
        if group is not None:
            group.discard(key)
            if not group:
                del self._by_file[(key[0], key[2], key[3])]
        self.nbytes -= size


_READ_MEMO = _ReadMemo()

#: Set by ``superset_reads()``: a shard may then be served from a stored read
#: of the same file under a larger symbol set, filtered to the symbols asked.
_SUPERSET_READS: ContextVar = ContextVar("pwb_superset_reads", default=False)


@contextmanager
def superset_reads():
    """Let the shard reads inside the block reuse a stored read of a larger
    symbol set.

    The rows are exactly those a direct read returns, in the same order. What
    can differ is the dtype of an integer column: pyarrow hands back ``int64``
    when the rows it converts hold no null and ``float64`` when one does, and a
    larger symbol set can hold a null the smaller one does not. So this is for
    callers that read float columns only -- the cost model's Roll fallback,
    which reads closes -- and never the default.
    """
    token = _SUPERSET_READS.set(True)
    try:
        yield
    finally:
        _SUPERSET_READS.reset(token)


def _file_ident(path: str):
    st = os.stat(path)
    return (path, st.st_size, st.st_mtime_ns, st.st_ino)


def _read_piece(path, symbols, columns, window, generation, budget) -> tuple[pd.DataFrame, bool]:
    """One shard through the memo: ``(frame, stored)``. A stored frame must
    not be handed to a caller as is."""
    if not budget or not isinstance(path, str):
        return _read_one_parquet(path, symbols, columns, window), False
    try:
        ident = _file_ident(path)
    except OSError:
        return _read_one_parquet(path, symbols, columns, window), False
    key = (
        ident,
        frozenset(symbols) if symbols else None,
        tuple(columns) if columns is not None else None,
        window.key() if window is not None else None,
    )
    hit = _READ_MEMO.get(key, generation)
    if hit is not None:
        return hit, True
    if _SUPERSET_READS.get():
        found = _READ_MEMO.get_superset(key, generation)
        if found is not None:
            frame, wanted = found
            sub = frame[frame["symbol"].isin(wanted)].reset_index(drop=True)
            return sub, False
    _READ_MEMO.misses += 1
    frame = _read_one_parquet(path, symbols, columns, window)
    _READ_MEMO.put(key, frame, generation, budget)
    return frame, True


def _read_parquet_files(paths: list[str], desc: str, symbols=None, columns=None, window=None) -> pd.DataFrame:
    if not paths:
        raise ValueError("No parquet files provided.")

    budget = _read_memo_budget()
    generation = _READ_MEMO.next_generation()
    iterator = tqdm(paths, desc=desc, unit="file") if len(paths) > 1 else paths
    frames = []
    stored = False
    for path in iterator:
        if isinstance(path, str) and path.startswith(("http://", "https://")):
            frames.append(_read_one_parquet(BytesIO(_http_get(path)), symbols, columns, window))
        else:
            frame, stored = _read_piece(path, symbols, columns, window, generation, budget)
            frames.append(frame)
    if len(frames) > 1:
        return pd.concat(frames, ignore_index=True)
    return frames[0].copy() if stored else frames[0]


# A shard named after the period it holds: ``train-2024``, ``train-2024-01``,
# ``train-2024-01-15``. The minute datasets are monthly (``data/train-YYYY-MM.parquet``).
_PERIOD_SHARD = re.compile(r"(?:^|/)(?P<split>[^/]+?)-(?P<period>\d{4}(?:-\d{2}){0,2})\.parquet$")


def _shard_period(name: str):
    """``(first instant, first instant after)`` of the period a shard is named
    after, or ``None`` when its name carries none. ``name`` may be a URL."""
    path = name.split("?", 1)[0]
    match = _PERIOD_SHARD.search(path)
    if not match:
        return None
    period = match.group("period")
    start = pd.Timestamp(period if len(period) > 4 else f"{period}-01-01")
    if len(period) == 4:
        return start, start + pd.DateOffset(years=1)
    if len(period) == 7:
        return start, start + pd.DateOffset(months=1)
    return start, start + pd.Timedelta(days=1)


def _shards_in_window(names: list, window, dataset_name: str) -> list:
    """The shards of ``names`` that can hold a row of ``window``, in order.

    Selected by the period in their names, before anything is downloaded.
    When a name carries no period the shards cannot be told apart without
    reading them: every one is kept, the rows outside the window are still
    dropped on read, and a warning says the download is not bounded.
    """
    if window is None:
        return list(names)
    periods = [_shard_period(n) for n in names]
    if not window.rows:
        # Picking shards for ``get_pricing``, which asked for no window of its
        # own: silent, and every shard when the names carry no period.
        if any(p is None for p in periods):
            return list(names)
        return [n for n, p in zip(names, periods) if window.overlaps(*p)]
    if any(p is None for p in periods):
        warnings.warn(
            f"The {len(names)} files of {dataset_name} carry no period in their names; all of "
            "them are downloaded and start/end only filter the rows read from each.",
            stacklevel=4,
        )
        return list(names)
    picked = [n for n, p in zip(names, periods) if window.overlaps(*p)]
    if not picked and periods:
        first = min(p[0] for p in periods).strftime("%Y-%m-%d")
        last = (max(p[1] for p in periods) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        warnings.warn(
            f"No shard of {dataset_name} covers {window.describe()}; the dataset covers "
            f"{first}..{last}. Nothing was downloaded.",
            stacklevel=4,
        )
    else:
        print(f"[datasets] {dataset_name} {window.describe()}: {len(picked)} of {len(names)} shards")
    return picked


#: The shard-picking window of the ``load_dataset`` call in progress, for its
#: loader only (see ``_SHARD_WINDOW`` below).
_LOADER_SHARD_WINDOW: ContextVar = ContextVar("pwb_loader_shard_window", default=None)


def _loader_window(window):
    """``window``, or else the shard-picking window ``get_pricing`` set."""
    if window is not None:
        return window
    picked = _LOADER_SHARD_WINDOW.get()
    if picked is not None:
        _LOADER_SHARD_WINDOW.set(None)
    return picked


def _row_window(window):
    """The window the rows are filtered on: none for a shard-picking one."""
    return window if window is not None and window.rows else None


def _empty_frame(columns=None) -> pd.DataFrame:
    keys = ["symbol"]
    return pd.DataFrame(columns=keys + [c for c in (columns or []) if c not in keys])


# --------------------------------------------------------------------------- #
# Subscriber API: a disk cache and parallel downloads                         #
# --------------------------------------------------------------------------- #
# Until 0.1.49 every ``load_dataset`` call through the API downloaded every
# shard again, one after the other: measured on 12 Nov 2026, 7 ETFs = 587 files,
# 328 MB, ~200 s at every call; 2 symbols of ``Stocks-Daily-Price`` = 779 files,
# 869 MB, 454 s. The Hub path, cached, reads the same 7 ETFs in 3.5 s.
#
# What the API tells about a file's version: its file list carries none, and a
# file answer carries an ``ETag`` (a content hash) -- one round trip per file,
# 0.4-0.7 s, as long as downloading a small shard. The datasets themselves are
# public (gated) on the Hub, whose metadata endpoint gives, in one anonymous
# request per dataset, the current commit and each file's size and SHA-256; and
# the API serves a file list pinned to a commit (``revision=<sha>``). So:
#
# * the file list is asked for at the Hub's current commit, and a file found in
#   the Hub's metadata is cached under its SHA-256 -- a content address: a new
#   commit that leaves a month untouched leaves its cached copy valid, and a
#   cached file is served without asking anything;
# * a file the metadata does not describe (a private dataset, the converted
#   index of a dataset stored as a single file, the Hub unreachable) is cached
#   under its dataset, path, ETag and size, read with a one-byte range request;
# * a file whose version cannot be told is downloaded and not cached.
#
# A download goes to a temporary file, is checked against the expected size
# (and SHA-256 when known), and only then renamed into place: a partial or
# corrupt file is never served. A cached file whose size differs from what is
# expected is downloaded again. Downloads run ``PWB_API_WORKERS`` at a time (4;
# eight drew 429s from the Hub behind the API, see ``_http_download``).
# The cache lives in ``$PWB_CACHE_DIR/api`` (``~/.cache/pwb_toolbox/api`` by
# default, ``$XDG_CACHE_HOME`` honoured), is capped at ``PWB_API_CACHE_MAX_GB``
# (10) with the least recently used files evicted first, and ``PWB_API_CACHE=0``
# turns it off.
#
# A symbol filter cannot cut the download: every published shard is a single
# row group holding every symbol of its period (checked on Stocks-Daily-Price
# and ETFs-Daily-Price), so there is no byte range to skip. Dates do: shards are
# named after their month and only the months of the window are fetched.
_API_BASE_URL = "https://data.paperswithbacktest.com/v1/datasets"
_API_WORKERS_DEFAULT = 4
_API_CACHE_MAX_GB_DEFAULT = 10.0
_API_INDEXES: dict = {}


def _api_cache_root():
    """The cache directory, or ``None`` when ``PWB_API_CACHE=0``."""
    if os.getenv("PWB_API_CACHE", "1").strip() == "0":
        return None
    root = os.getenv("PWB_CACHE_DIR")
    if not root:
        base = os.getenv("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        root = os.path.join(base, "pwb_toolbox")
    return os.path.join(root, "api")


def _env_number(name, default, cast=float):
    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError):
        return cast(default)


def _api_file_index(dataset_name: str):
    """``(commit, {path: (size, sha256)})`` of the dataset on the Hub, or ``None``.

    One anonymous metadata request per dataset and per process (the published
    datasets are public, gated: their metadata needs no account). ``None`` when
    the Hub is not consulted (``PWB_HF_OFFLINE``, ``HF_HUB_OFFLINE``,
    ``PWB_API_HUB_INDEX=0``) or does not answer.
    """
    if dataset_name in _API_INDEXES:
        return _API_INDEXES[dataset_name]
    out = None
    offline = (
        os.getenv("PWB_HF_OFFLINE", "0") != "0"
        or os.getenv("HF_HUB_OFFLINE", "0") not in ("", "0")
        or os.getenv("PWB_API_HUB_INDEX", "1").strip() == "0"
    )
    if not offline:
        try:
            info = HfApi(token=os.getenv("HF_ACCESS_TOKEN") or False).dataset_info(
                f"paperswithbacktest/{dataset_name}", files_metadata=True, timeout=30
            )
            files = {}
            for sibling in info.siblings or []:
                lfs = sibling.lfs
                sha = None
                if lfs is not None:
                    sha = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
                if sha and sibling.size:
                    files[sibling.rfilename] = (int(sibling.size), str(sha))
            if info.sha and files:
                out = (info.sha, files)
        except Exception:  # noqa: BLE001 - the ETag route is the fallback
            out = None
    _API_INDEXES[dataset_name] = out
    return out


def _api_listing(dataset_name: str, split: str, pwb_api_key: str, revision=None) -> list:
    params = {"pwb_api_key": pwb_api_key, "split": split}
    if revision:
        params["revision"] = revision
    resp = requests.get(f"{_API_BASE_URL}/{dataset_name}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("files", [])


def _api_file_path(url: str, dataset_name: str):
    """``(repository path, revision)`` of an API file URL; the path is ``None``
    for a file of the Hub's converted index (``/parquet/...``)."""
    parsed = urlparse(url)
    prefix = f"/v1/datasets/{dataset_name}/"
    path = parsed.path[len(prefix):] if parsed.path.startswith(prefix) else None
    if path is not None and path.startswith("parquet/"):
        path = None
    revision = dict(parse_qsl(parsed.query)).get("revision")
    return path, revision


def _api_probe(url: str):
    """``(etag, size)`` of a file, from a one-byte range request; ``None`` when
    the answer does not carry both."""
    for throttled in range(1, _HTTP_429_ATTEMPTS + 1):
        _api_gate_wait()
        try:
            resp = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=_HTTP_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException:
            return None
        if resp.status_code != 429:
            break
        resp.close()
        _api_gate_close(resp, throttled)
    else:
        return None
    try:
        etag = resp.headers.get("ETag") or resp.headers.get("etag")
        if resp.status_code == 206:
            total = (resp.headers.get("Content-Range") or "").rsplit("/", 1)[-1]
        elif resp.status_code == 200:
            total = resp.headers.get("Content-Length")
        else:
            return None
        if not etag or not str(total).isdigit():
            return None
        return etag.strip().strip('"'), int(total)
    finally:
        resp.close()


# Too many requests: the API answers 429 when the Hub behind it throttles its
# token, which every subscriber shares. Measured on 12 Nov 2026: eight parallel
# downloads, right after ~3 400 other file requests on the same token, drew 429s
# within the minute, and four retries 2-8 s apart were not enough to see the
# window reopen. So a 429 pauses every download of the process (the gate below),
# for the ``Retry-After`` the answer gives or 30 s doubling up to 5 min, and is
# retried up to ``_HTTP_429_ATTEMPTS`` times; other failures keep the policy of
# ``_http_get``.
_HTTP_429_ATTEMPTS = 8
_HTTP_429_WAIT_SECONDS = 30.0
_HTTP_429_MAX_WAIT_SECONDS = 300.0
_API_GATE = {"until": 0.0}
_API_GATE_LOCK = threading.Lock()


def _api_gate_wait() -> None:
    while True:
        with _API_GATE_LOCK:
            delay = _API_GATE["until"] - time.monotonic()
        if delay <= 0:
            return
        time.sleep(min(delay, 5.0))


def _api_gate_close(resp, throttled: int) -> None:
    wait = None
    header = (resp.headers.get("Retry-After") if resp is not None else None) or ""
    if header.strip().isdigit():
        wait = float(header.strip())
    if wait is None:
        wait = _HTTP_429_WAIT_SECONDS * 2 ** (throttled - 1)
    wait = min(wait, _HTTP_429_MAX_WAIT_SECONDS)
    with _API_GATE_LOCK:
        _API_GATE["until"] = max(_API_GATE["until"], time.monotonic() + wait)


def _redact_key(text: str) -> str:
    return re.sub(r"(pwb_api_key=)[^&\s]+", r"\1***", str(text))


def _http_download(url: str, fh) -> tuple[int, str]:
    """Stream ``url`` into the open file ``fh``: ``(bytes, sha256)``.

    The retry policy of ``_http_get``, except for a 429 (see above); a retry
    starts the file over. An error never carries the API key.
    """
    import hashlib

    last_exc = None
    failures = throttled = 0
    while True:
        _api_gate_wait()
        fh.seek(0)
        fh.truncate()
        digest = hashlib.sha256()
        size = 0
        resp = None
        try:
            with requests.get(url, stream=True, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            return size, digest.hexdigest()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 429:
                throttled += 1
                last_exc = exc
                if throttled >= _HTTP_429_ATTEMPTS:
                    break
                _api_gate_close(exc.response, throttled)
                continue
            if status is not None and status < 500:
                raise requests.exceptions.HTTPError(_redact_key(exc), response=exc.response) from None
            last_exc = exc
        except requests.exceptions.RequestException as exc:
            last_exc = exc
        failures += 1
        if failures >= _HTTP_ATTEMPTS:
            break
        time.sleep(_HTTP_BACKOFF_SECONDS * 2 ** (failures - 1))
    raise type(last_exc)(_redact_key(last_exc)) from None


class _CorruptDownload(IOError):
    pass


def _api_fetch(url: str, root, cache_name, expect):
    """One file: a cached path, or a fresh download (``(source, was_cached)``).

    ``cache_name`` is the file's name in the cache (``None``: not cacheable);
    ``expect`` is ``(size, sha256 or None)``.
    """
    if root is None or cache_name is None:
        return BytesIO(_http_get(url)), False
    final = os.path.join(root, "blobs", cache_name)
    size, sha = expect
    try:
        if os.path.getsize(final) == size:
            os.utime(final, None)  # least recently used goes first
            return final, True
    except OSError:
        pass
    tmpdir = os.path.join(root, "tmp")
    os.makedirs(tmpdir, exist_ok=True)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="dl-", suffix=".part", dir=tmpdir)
    try:
        with os.fdopen(fd, "w+b") as fh:
            got, digest = _http_download(url, fh)
            fh.flush()
            os.fsync(fh.fileno())
        if got != size or (sha is not None and digest != sha):
            raise _CorruptDownload(
                f"{cache_name}: got {got} bytes"
                + (f", sha256 {digest[:12]}" if sha is not None else "")
                + f"; expected {size}" + (f", sha256 {sha[:12]}" if sha is not None else "")
            )
        os.replace(tmp, final)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return final, False


def _api_cache_evict(root, keep) -> None:
    """Delete the least recently used files until the cache fits its cap,
    never one of ``keep``; and temporary files a dead process left behind."""
    cap = _env_number("PWB_API_CACHE_MAX_GB", _API_CACHE_MAX_GB_DEFAULT) * 1024**3
    blobs = os.path.join(root, "blobs")
    entries = []
    try:
        with os.scandir(blobs) as it:
            for entry in it:
                try:
                    st = entry.stat()
                except OSError:
                    continue
                entries.append((st.st_mtime, st.st_size, entry.path))
    except OSError:
        return
    total = sum(e[1] for e in entries)
    keep = {os.path.abspath(k) for k in keep}
    for _mtime, size, path in sorted(entries):
        if total <= cap:
            break
        if os.path.abspath(path) in keep:
            continue
        try:
            os.unlink(path)
            total -= size
        except OSError:
            pass
    tmpdir = os.path.join(root, "tmp")
    cutoff = time.time() - 24 * 3600
    try:
        with os.scandir(tmpdir) as it:
            for entry in it:
                try:
                    if entry.stat().st_mtime < cutoff:
                        os.unlink(entry.path)
                except OSError:
                    pass
    except OSError:
        pass


def _api_fetch_all(dataset_name: str, urls: list, index, root) -> list:
    """Every file of ``urls``, in order: cached paths or in-memory downloads."""
    import hashlib
    from concurrent.futures import ThreadPoolExecutor

    plans = []
    for url in urls:
        path, revision = _api_file_path(url, dataset_name)
        meta = None
        if index is not None and path is not None and revision == index[0]:
            meta = index[1].get(path)
        if meta is not None:
            plans.append((url, f"sha256-{meta[1]}.parquet", meta))
        else:
            plans.append((url, None, None))

    def run(plan):
        # A download that does not match what was expected is tried once more
        # (re-probed: an unpinned file may have changed in between), then fails.
        for attempt in (1, 2):
            url, name, expect = plan
            if root is not None and name is None:
                probe = _api_probe(url)
                if probe is not None:
                    etag, size = probe
                    where = path_of(url)
                    key = hashlib.sha256(f"{dataset_name}\n{where}\n{etag}\n{size}".encode()).hexdigest()
                    name, expect = f"etag-{key}.parquet", (size, None)
            try:
                return _api_fetch(url, root, name, expect)
            except _CorruptDownload:
                if attempt == 2:
                    raise

    def path_of(url):
        path, _ = _api_file_path(url, dataset_name)
        return path if path is not None else urlparse(url).path

    workers = max(1, min(int(_env_number("PWB_API_WORKERS", _API_WORKERS_DEFAULT, int)), len(plans)))
    results = [None] * len(plans)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, plan): i for i, plan in enumerate(plans)}
        done = tqdm(total=len(plans), desc=f"PWB {dataset_name}", unit="file", disable=len(plans) < 2)
        try:
            from concurrent.futures import as_completed

            for future in as_completed(futures):
                results[futures[future]] = future.result()
                done.update(1)
        except BaseException:
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        finally:
            done.close()
    cached = sum(1 for _, was_cached in results if was_cached)
    stored = [src for src, _ in results if isinstance(src, str)]
    print(f"PWB {dataset_name}: {len(plans)} files, {cached} from the local cache, "
          f"{len(plans) - cached} downloaded")
    if root is not None and stored:
        _api_cache_evict(root, stored)
    return [src for src, _ in results]


def _load_dataset_from_pwb(dataset_name: str, split: str, pwb_api_key: str, symbols=None,
                           columns=None, window=None) -> pd.DataFrame:
    root = _api_cache_root()
    index = _api_file_index(dataset_name) if root is not None else None
    files = None
    if index is not None:
        try:
            files = _api_listing(dataset_name, split, pwb_api_key, revision=index[0])
        except Exception:  # noqa: BLE001 - an API that does not pin: plain list
            files, index = None, None
    if files is None:
        files = _api_listing(dataset_name, split, pwb_api_key)
    if not files:
        raise ValueError(f"No files available for dataset '{dataset_name}' and split '{split}'")

    window = _loader_window(window)
    files = _shards_in_window(files, window, dataset_name)
    if not files:
        return _empty_frame(columns)
    sources = _api_fetch_all(dataset_name, files, index, root)
    return _read_parquet_files(sources, desc=f"Load {dataset_name}", symbols=symbols,
                               columns=columns, window=_row_window(window))


def _list_hf_split_parquet_files(repo_files: list[str], split: str) -> list[str]:
    # Shards named after the period they hold (``train-2024-01``, ``train-2010``)
    # win over every other layout. A repository holding both is one whose
    # layout changed and whose old files stayed: ``All-Daily-News`` on
    # 2026-11-08 had six ``train-0000k-of-00006`` files (2022-03 to 2026-07-01)
    # next to 57 monthly ones (2022-03 to 2026-11), the same rows twice.
    dated = re.compile(rf"(^|/){re.escape(split)}-\d{{4}}(-\d{{2}}){{0,2}}\.parquet$")
    matched = [f for f in repo_files if dated.search(f)]
    if matched:
        return sorted(matched)

    patterns = [
        re.compile(rf"(^|/){re.escape(split)}-\d{{5}}-of-\d{{5}}\.parquet$"),
        re.compile(rf"(^|/){re.escape(split)}\.parquet$"),
    ]
    matched = [f for f in repo_files if any(p.search(f) for p in patterns)]
    if matched:
        return sorted(matched)

    # Fallback for unusual naming conventions.
    return sorted([f for f in repo_files if f.endswith(".parquet") and f"/{split}" in f])


_HUB_SNAPSHOTS: dict = {}


def _local_snapshot(repo_id: str):
    """The newest snapshot of ``repo_id`` in the Hub cache: ``(sha, files)``, or ``None``."""
    root = os.path.join(HF_HUB_CACHE, f"datasets--{repo_id.replace('/', '--')}", "snapshots")
    if not os.path.isdir(root):
        return None
    snapshots = [os.path.join(root, d) for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    if not snapshots:
        return None
    newest = max(snapshots, key=os.path.getmtime)
    files = []
    for dirpath, _dirs, names in os.walk(newest):
        for name in names:
            files.append(os.path.relpath(os.path.join(dirpath, name), newest))
    return os.path.basename(newest), sorted(files)


def _hub_snapshot(repo_id: str, hf_token: str):
    """``(sha, files)`` of the dataset's current revision: one Hub request per
    dataset and per process, none at all with ``PWB_HF_OFFLINE=1``.

    The previous loader asked the Hub for the file list, then let
    ``hf_hub_download`` revalidate every shard against the Hub before reading
    it from the cache: 778 shards for the daily stock prices, one HTTPS round
    trip each, 173 s of a 187 s load on a warm cache (measured 30 Oct 2026,
    ``_ssl.SSLSocket.read`` 802 calls), against 1 s to read the parquet files.
    Pinning the revision to the commit hash lets ``hf_hub_download`` return a
    cached file without a request; a new commit on the Hub changes the hash and
    downloads what it must. Offline, or when the Hub is unreachable, the newest
    local snapshot is used and said so.
    """
    if repo_id in _HUB_SNAPSHOTS:
        return _HUB_SNAPSHOTS[repo_id]
    offline = os.getenv("PWB_HF_OFFLINE", "0") != "0" or os.getenv("HF_HUB_OFFLINE", "0") not in ("", "0")
    if not offline:
        try:
            info = HfApi(token=hf_token).dataset_info(repo_id, files_metadata=False)
            snapshot = (info.sha, sorted(sibling.rfilename for sibling in info.siblings))
            _HUB_SNAPSHOTS[repo_id] = snapshot
            return snapshot
        except Exception as exc:  # noqa: BLE001 - the local copy is the fallback
            print(f"[datasets] Hub unreachable for {repo_id} ({type(exc).__name__}); using the local snapshot")
    snapshot = _local_snapshot(repo_id)
    if snapshot is None:
        raise RuntimeError(
            f"No local snapshot of {repo_id} in {HF_HUB_CACHE} and the Hub was not consulted "
            f"(offline={offline})."
        )
    _HUB_SNAPSHOTS[repo_id] = snapshot
    return snapshot


def _load_dataset_from_hf(dataset_name: str, split: str, hf_token: str, symbols=None,
                          columns=None, window=None) -> pd.DataFrame:
    repo_id = f"paperswithbacktest/{dataset_name}"
    sha, repo_files = _hub_snapshot(repo_id, hf_token)
    parquet_files = _list_hf_split_parquet_files(repo_files, split)
    if not parquet_files:
        raise ValueError(f"No parquet files found for split '{split}' in dataset '{repo_id}'.")
    # Only the shards of the window are downloaded: a month of 1-minute stock
    # bars is ~350 MB, the whole table ~75 GB.
    window = _loader_window(window)
    parquet_files = _shards_in_window(parquet_files, window, dataset_name)
    if not parquet_files:
        return _empty_frame(columns)

    iterator = tqdm(parquet_files, desc=f"HF {dataset_name}", unit="file") if len(parquet_files) > 1 else parquet_files
    local_files = [
        hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename=file_name,
            revision=sha,
            token=hf_token,
        )
        for file_name in iterator
    ]
    return _read_parquet_files(local_files, desc=f"Load {dataset_name}", symbols=symbols,
                               columns=columns, window=_row_window(window))

DAILY_PRICE_DATASETS = [
    "Bonds-Daily-Price",
    "Commodities-Daily-Price",
    "Cryptocurrencies-Daily-Price",
    "ETFs-Daily-Price",
    "Forex-Daily-Price",
    "Indices-Daily-Price",
    "Preferreds-Daily-Price",
    "Stocks-Daily-Price",
    "StructuredProducts-Daily-Price",
    "Warrants-Daily-Price",
]


#: The index composition as of 2026, frozen. Reached through the explicit
#: ``"sp500-frozen"`` pseudo-symbol, and nothing else should use it: replaying
#: today's 503 members over an earlier period is look-ahead twice over -- it
#: holds names that had not yet been added, and it never holds the names that
#: mattered then and have since been removed or delisted. ``"sp500"`` resolves
#: to the point-in-time universe instead (see ``pit_universe``); this list is
#: kept so the difference between the two can be measured rather than argued.
SP500_SYMBOLS = [
    "MMM",
    "AOS",
    "ABT",
    "ABBV",
    "ACN",
    "ADBE",
    "AMD",
    "AES",
    "AFL",
    "A",
    "APD",
    "ABNB",
    "AKAM",
    "ALB",
    "ARE",
    "ALGN",
    "ALLE",
    "LNT",
    "ALL",
    "GOOGL",
    "GOOG",
    "MO",
    "AMZN",
    "AMCR",
    "AEE",
    "AEP",
    "AXP",
    "AIG",
    "AMT",
    "AWK",
    "AMP",
    "AME",
    "AMGN",
    "APH",
    "ADI",
    "ANSS",
    "AON",
    "APA",
    "AAPL",
    "AMAT",
    "APTV",
    "ACGL",
    "ADM",
    "ANET",
    "AJG",
    "AIZ",
    "T",
    "ATO",
    "ADSK",
    "ADP",
    "AZO",
    "AVB",
    "AVY",
    "AXON",
    "BKR",
    "BALL",
    "BAC",
    "BK",
    "BBWI",
    "BAX",
    "BDX",
    "BRK-B",
    "BBY",
    "TECH",
    "BIIB",
    "BLK",
    "BX",
    "BA",
    "BKNG",
    "BWA",
    "BSX",
    "BMY",
    "AVGO",
    "BR",
    "BRO",
    "BF-B",
    "BLDR",
    "BG",
    "BXP",
    "CHRW",
    "CDNS",
    "CZR",
    "CPT",
    "CPB",
    "COF",
    "CAH",
    "KMX",
    "CCL",
    "CARR",
    "CTLT",
    "CAT",
    "CBOE",
    "CBRE",
    "CDW",
    "CE",
    "COR",
    "CNC",
    "CNP",
    "CF",
    "CRL",
    "SCHW",
    "CHTR",
    "CVX",
    "CMG",
    "CB",
    "CHD",
    "CI",
    "CINF",
    "CTAS",
    "CSCO",
    "C",
    "CFG",
    "CLX",
    "CME",
    "CMS",
    "KO",
    "CTSH",
    "CL",
    "CMCSA",
    "CAG",
    "COP",
    "ED",
    "STZ",
    "CEG",
    "COO",
    "CPRT",
    "GLW",
    "CPAY",
    "CTVA",
    "CSGP",
    "COST",
    "CTRA",
    "CRWD",
    "CCI",
    "CSX",
    "CMI",
    "CVS",
    "DHR",
    "DRI",
    "DVA",
    "DAY",
    "DECK",
    "DE",
    "DELL",
    "DAL",
    "DVN",
    "DXCM",
    "FANG",
    "DLR",
    "DFS",
    "DG",
    "DLTR",
    "D",
    "DPZ",
    "DOV",
    "DOW",
    "DHI",
    "DTE",
    "DUK",
    "DD",
    "EMN",
    "ETN",
    "EBAY",
    "ECL",
    "EIX",
    "EW",
    "EA",
    "ELV",
    "EMR",
    "ENPH",
    "ETR",
    "EOG",
    "EPAM",
    "EQT",
    "EFX",
    "EQIX",
    "EQR",
    "ERIE",
    "ESS",
    "EL",
    "EG",
    "EVRG",
    "ES",
    "EXC",
    "EXPE",
    "EXPD",
    "EXR",
    "XOM",
    "FFIV",
    "FDS",
    "FICO",
    "FAST",
    "FRT",
    "FDX",
    "FIS",
    "FITB",
    "FSLR",
    "FE",
    "FI",
    "FMC",
    "F",
    "FTNT",
    "FTV",
    "FOXA",
    "FOX",
    "BEN",
    "FCX",
    "GRMN",
    "IT",
    "GE",
    "GEHC",
    "GEV",
    "GEN",
    "GNRC",
    "GD",
    "GIS",
    "GM",
    "GPC",
    "GILD",
    "GPN",
    "GL",
    "GDDY",
    "GS",
    "HAL",
    "HIG",
    "HAS",
    "HCA",
    "DOC",
    "HSIC",
    "HSY",
    "HES",
    "HPE",
    "HLT",
    "HOLX",
    "HD",
    "HON",
    "HRL",
    "HST",
    "HWM",
    "HPQ",
    "HUBB",
    "HUM",
    "HBAN",
    "HII",
    "IBM",
    "IEX",
    "IDXX",
    "ITW",
    "INCY",
    "IR",
    "PODD",
    "INTC",
    "ICE",
    "IFF",
    "IP",
    "IPG",
    "INTU",
    "ISRG",
    "IVZ",
    "INVH",
    "IQV",
    "IRM",
    "JBHT",
    "JBL",
    "JKHY",
    "J",
    "JNJ",
    "JCI",
    "JPM",
    "JNPR",
    "K",
    "KVUE",
    "KDP",
    "KEY",
    "KEYS",
    "KMB",
    "KIM",
    "KMI",
    "KKR",
    "KLAC",
    "KHC",
    "KR",
    "LHX",
    "LH",
    "LRCX",
    "LW",
    "LVS",
    "LDOS",
    "LEN",
    "LLY",
    "LIN",
    "LYV",
    "LKQ",
    "LMT",
    "L",
    "LOW",
    "LULU",
    "LYB",
    "MTB",
    "MRO",
    "MPC",
    "MKTX",
    "MAR",
    "MMC",
    "MLM",
    "MAS",
    "MA",
    "MTCH",
    "MKC",
    "MCD",
    "MCK",
    "MDT",
    "MRK",
    "META",
    "MET",
    "MTD",
    "MGM",
    "MCHP",
    "MU",
    "MSFT",
    "MAA",
    "MRNA",
    "MHK",
    "MOH",
    "TAP",
    "MDLZ",
    "MPWR",
    "MNST",
    "MCO",
    "MS",
    "MOS",
    "MSI",
    "MSCI",
    "NDAQ",
    "NTAP",
    "NFLX",
    "NEM",
    "NWSA",
    "NWS",
    "NEE",
    "NKE",
    "NI",
    "NDSN",
    "NSC",
    "NTRS",
    "NOC",
    "NCLH",
    "NRG",
    "NUE",
    "NVDA",
    "NVR",
    "NXPI",
    "ORLY",
    "OXY",
    "ODFL",
    "OMC",
    "ON",
    "OKE",
    "ORCL",
    "OTIS",
    "PCAR",
    "PKG",
    "PLTR",
    "PANW",
    "PARA",
    "PH",
    "PAYX",
    "PAYC",
    "PYPL",
    "PNR",
    "PEP",
    "PFE",
    "PCG",
    "PM",
    "PSX",
    "PNW",
    "PNC",
    "POOL",
    "PPG",
    "PPL",
    "PFG",
    "PG",
    "PGR",
    "PLD",
    "PRU",
    "PEG",
    "PTC",
    "PSA",
    "PHM",
    "QRVO",
    "PWR",
    "QCOM",
    "DGX",
    "RL",
    "RJF",
    "RTX",
    "O",
    "REG",
    "REGN",
    "RF",
    "RSG",
    "RMD",
    "RVTY",
    "ROK",
    "ROL",
    "ROP",
    "ROST",
    "RCL",
    "SPGI",
    "CRM",
    "SBAC",
    "SLB",
    "STX",
    "SRE",
    "NOW",
    "SHW",
    "SPG",
    "SWKS",
    "SJM",
    "SW",
    "SNA",
    "SOLV",
    "SO",
    "LUV",
    "SWK",
    "SBUX",
    "STT",
    "STLD",
    "STE",
    "SYK",
    "SMCI",
    "SYF",
    "SNPS",
    "SYY",
    "TMUS",
    "TROW",
    "TTWO",
    "TPR",
    "TRGP",
    "TGT",
    "TEL",
    "TDY",
    "TFX",
    "TER",
    "TSLA",
    "TXN",
    "TXT",
    "TMO",
    "TJX",
    "TSCO",
    "TT",
    "TDG",
    "TRV",
    "TRMB",
    "TFC",
    "TYL",
    "TSN",
    "USB",
    "UBER",
    "UDR",
    "ULTA",
    "UNP",
    "UAL",
    "UPS",
    "URI",
    "UNH",
    "UHS",
    "VLO",
    "VTR",
    "VLTO",
    "VRSN",
    "VRSK",
    "VZ",
    "VRTX",
    "VTRS",
    "VICI",
    "V",
    "VST",
    "VMC",
    "WRB",
    "GWW",
    "WAB",
    "WBA",
    "WMT",
    "DIS",
    "WBD",
    "WM",
    "WAT",
    "WEC",
    "WFC",
    "WELL",
    "WST",
    "WDC",
    "WY",
    "WMB",
    "WTW",
    "WYNN",
    "XEL",
    "XYL",
    "YUM",
    "ZBRA",
    "ZBH",
    "ZTS",
]


#: Size of the point-in-time universe ``"sp500"`` resolves to. 500 to match
#: what the papers using ``"sp500"`` mean by "large US equities"; the published
#: table carries ranks up to 1000, so this is the only line to change.
SP500_PIT_TOP_N = 500

#: The pseudo-symbols that name a point-in-time liquidity universe, and the
#: rank they cut at. ``"sp500"`` is the historical name; ``"liquid1000"`` is the
#: same table read to its full depth, for the papers whose cross-section is the
#: liquid mid-cap market rather than its top -- industry reversals, the
#: small-stock premium, anything that sorts on characteristics within a wide
#: panel. Both are enforced per date by :func:`pit_universe.apply_pit_membership`.
#:
#: Each value is ``(top_n, min_months)``: the rank the universe cuts at, and
#: the point-in-time tenure a name needs before it counts (see
#: :func:`pit_universe.load_pit_universe`). ``"liquid1000"`` carries a
#: twelve-month floor because the strategies written for a wide cross-section
#: cannot afford a feed per brief visitor: 3,954 names ever in the top 1000
#: against 2,674 with a year of tenure, and the backtest time follows the
#: feed count.
PIT_UNIVERSES = {
    "sp500": (SP500_PIT_TOP_N, 0),
    "liquid1000": (1000, 12),
}


def _resolve_universe(symbols):
    """Expand the universe pseudo-symbols, and say whether to filter per date.

    Returns ``(symbol_filter, pit_spec, pit_added, explicit)``:

    * ``pit_spec`` is ``None`` unless a point-in-time universe was asked for
      (``"sp500"`` or ``"liquid1000"``, see :data:`PIT_UNIVERSES`), in which
      case it is the ``(top_n, min_months)`` pair and the caller must also run
      :func:`pit_universe.apply_pit_membership` with it on the loaded frame. Asking for both in one call is refused: they would
      need two different per-date cuts on the same frame. The expansion here only widens the *load* to every name
      that ever belonged; it is the per-date pass that keeps each one to its
      own window.
    * ``pit_added`` is the set the universe contributed. ``get_pricing`` needs
      it because ``Universe-Daily-Price`` does not know these symbols: it
      indexes 21 117 names while ``Stocks-Daily-Price`` carries 36 676 since
      the delisted half was merged in. 553 of the 2 013 point-in-time names --
      AABA, ABK, AET, AGN, ALTR, AKS, the bought-out and the bankrupt -- have no
      row in the index, and routing by it alone would drop a quarter of the
      universe behind a ``Warning`` nobody reads during a 4 178-backtest
      campaign. They are US common stocks by construction, so they route
      straight to ``Stocks-Daily-Price``.
    * ``explicit`` is what the caller named itself, pseudo-symbols aside. The
      per-date cut must spare these: ``["sp500", "SPY"]`` means the members by
      date plus SPY on every date, and SPY was never a member. Applied to the
      whole frame, the cut used to delete every such hedge or benchmark, and
      the strategy then died on a missing feed or ran unhedged.
    """
    out = list(symbols)

    if "sp500-frozen" in out:
        out.remove("sp500-frozen")
        out += SP500_SYMBOLS

    pit_top_n = None
    pit_added = frozenset()
    asked = [name for name in PIT_UNIVERSES if name in out]
    if len(asked) > 1:
        raise ValueError(
            f"{asked} name two point-in-time universes of different depth; "
            "load them in two calls, each gets its own per-date membership"
        )
    explicit = frozenset(s for s in out if s not in PIT_UNIVERSES)
    if asked:
        from .pit_universe import pit_symbols

        name = asked[0]
        out.remove(name)
        pit_top_n = PIT_UNIVERSES[name]
        pit_added = frozenset(pit_symbols(*pit_top_n))
        out += sorted(pit_added - explicit)

    return out, pit_top_n, pit_added, explicit


# ---------------------------------------------------------------- forex pairs
#
# ``Forex-Daily-Price`` carries each currency pair under ONE spelling once the
# table is republished from data-api #52: the one whose series starts first
# (``USDJPY`` since 1971, ``XAUUSD`` since 1970). Until then 27 pairs sit in the
# table twice -- the long series and a stub of the other spelling (``JPYUSD``
# since 2009, ``USDXAU``...) -- and ``to_usd`` renamed the long one onto the
# stub's name, so every common date loaded twice. After the republication the
# stubs are gone, and a strategy that names one (``symbols=["JPYUSD"]``) would
# receive nothing, without an error.
#
# The loader therefore resolves a pair, not a spelling. It always reads both
# spellings of every name it is asked for, keeps the one series the published
# rule keeps (the same rule as data-api ``public/forex/pairs.py``, so the table
# before and after the republication loads identically), and serves the name
# that was asked for from it, inverted when the spellings differ.
FOREX_DAILY_DATASET = "Forex-Daily-Price"

#: Columns a quote inversion maps to ``1 / x`` in place.
_INVERTED_IN_PLACE = ("open", "close", "adj_open", "adj_close")
#: Columns that trade places under ``1 / x``: the day's low of USD/JPY is the
#: day's high of JPY/USD. Inverting them in place leaves ``high < low`` on every
#: bar, which is what ``to_usd`` used to hand back for the 29 inverted pairs.
_INVERTED_SWAPPED = (("high", "low"), ("adj_high", "adj_low"))


def forex_inverse(symbol) -> str:
    """``USDJPY`` -> ``JPYUSD``. A name that is not two 3-letter codes is its own inverse."""
    name = str(symbol)
    if len(name) != 6 or not name.isalpha():
        return name
    return name[3:] + name[:3]


def _invert_quotes(frame: pd.DataFrame) -> pd.DataFrame:
    """Prices of the inverse pair: ``1/x`` for open/close, high and low swapped.

    Volume and every other column are left as they are. Works on a copy.
    """
    out = frame.copy()
    for col in _INVERTED_IN_PLACE:
        if col in out.columns:
            out[col] = 1.0 / out[col].astype("float64")
    for high, low in _INVERTED_SWAPPED:
        if high in out.columns and low in out.columns:
            hi = 1.0 / out[low].astype("float64")
            lo = 1.0 / out[high].astype("float64")
            out[high], out[low] = hi, lo
        else:
            for col in (high, low):
                if col in out.columns:
                    out[col] = 1.0 / out[col].astype("float64")
    return out


def forex_shadow_directions(frame: pd.DataFrame) -> dict:
    """``{dropped: kept}`` for every pair present under both spellings.

    The rule of data-api ``public/forex/pairs.py``: the spelling whose series
    starts first, then the one with more rows, then the ``USD``-first one.
    Empty once the table is republished, since it then holds one spelling per
    pair; until then it names the 27 stubs (``JPYUSD``, ``USDXAU``...).
    """
    if frame.empty or "symbol" not in frame.columns or "date" not in frame.columns:
        return {}
    dates = pd.to_datetime(frame["date"])
    span = dates.groupby(frame["symbol"]).agg(["min", "count"])
    symbols = set(span.index)
    out = {}
    for symbol in sorted(symbols):
        other = forex_inverse(symbol)
        if other == symbol or other not in symbols or symbol in out or other in out:
            continue
        a, b = span.loc[symbol], span.loc[other]
        key_a = (a["min"], -int(a["count"]), not symbol.startswith("USD"))
        key_b = (b["min"], -int(b["count"]), not other.startswith("USD"))
        kept, dropped = (symbol, other) if key_a <= key_b else (other, symbol)
        out[dropped] = kept
    return out


def _forex_widen_filter(symbol_filter):
    """The names to read for a request: each one and its inverse."""
    if symbol_filter is None:
        return None
    out = list(symbol_filter)
    seen = set(out)
    for symbol in symbol_filter:
        other = forex_inverse(symbol)
        if other not in seen:
            out.append(other)
            seen.add(other)
    return out


def _forex_resolve_directions(df: pd.DataFrame, requested, to_usd: bool) -> pd.DataFrame:
    """One series per pair, served under the requested names.

    ``df`` is the raw read of the requested names and their inverses.

    * The shadow spelling of a pair present twice is dropped first (see
      :func:`forex_shadow_directions`), so the published table before and
      after data-api #52 gives the same answer.
    * ``to_usd=True`` stops there: the conversion that follows renames every
      pair to ``XXXUSD`` and inverts what needs it, so asking for ``JPYUSD``,
      ``USDJPY`` or both yields the one ``JPYUSD`` series, never two and never
      inverted twice.
    * ``to_usd=False`` returns each requested name as spelled: the raw rows
      when the table keeps that spelling, the inverted rows of the kept
      spelling otherwise (``JPYUSD`` from ``USDJPY``). A pair asked for under
      both spellings comes back under both, one the inverse of the other.
    """
    if df.empty or "symbol" not in df.columns:
        return df
    shadows = forex_shadow_directions(df)
    if shadows:
        df = df[~df["symbol"].isin(shadows)]
    if to_usd or requested is None:
        return df.reset_index(drop=True)

    present = set(df["symbol"].unique())
    frames = []
    for symbol in dict.fromkeys(requested):
        if symbol in present:
            frames.append(df[df["symbol"] == symbol])
            continue
        other = forex_inverse(symbol)
        if other != symbol and other in present:
            inverted = _invert_quotes(df[df["symbol"] == other])
            inverted["symbol"] = symbol
            frames.append(inverted)
    if not frames:
        return df.iloc[0:0].reset_index(drop=True)
    return pd.concat(frames, ignore_index=True)


def _forex_to_usd(df: pd.DataFrame) -> pd.DataFrame:
    """Every pair quoted as dollars per unit of the other currency, named ``XXXUSD``.

    ``USDJPY`` at 158 becomes ``JPYUSD`` at 0.0063; a pair already ending in
    ``USD`` is left alone. High and low are swapped by the inversion, see
    :func:`_invert_quotes`.
    """
    if df.empty or "symbol" not in df.columns:
        return df
    flip = ~df["symbol"].astype(str).str.endswith("USD")
    if not flip.any():
        return df
    df = df.copy()
    inverted = _invert_quotes(df.loc[flip])
    inverted["symbol"] = inverted["symbol"].astype(str).str[3:] + "USD"
    df.loc[flip] = inverted
    return df


def _with_forex_inverse_names(universe: pd.DataFrame) -> pd.DataFrame:
    """The catalogue index, plus each forex pair under its other spelling.

    The loader answers ``JPYUSD`` from ``USDJPY`` (see
    :func:`_forex_resolve_directions`), so the index must route both spellings
    to ``Forex-Daily-Price``: ``get_pricing`` and the cost model look a bare
    name up there, and after the republication drops the 27 stubs from the
    index ``JPYUSD`` would otherwise be "no dataset found". A spelling the index
    already knows, under any repository, is never overridden.
    """
    if universe.empty or not {"symbol", "repo_id"}.issubset(universe.columns):
        return universe
    is_fx = universe["repo_id"].astype(str).str.split("/").str[-1] == FOREX_DAILY_DATASET
    fx = universe[is_fx]
    if fx.empty:
        return universe
    known = set(universe["symbol"].astype(str))
    alias = fx.assign(symbol=fx["symbol"].astype(str).map(forex_inverse))
    alias = alias[(alias["symbol"] != fx["symbol"].astype(str)) & ~alias["symbol"].isin(known)]
    alias = alias.drop_duplicates("symbol")
    if alias.empty:
        return universe
    return pd.concat([universe, alias], ignore_index=True)


class UnboundedMinuteLoadWarning(UserWarning):
    """A minute dataset was loaded without ``start``/``end``: every monthly
    shard is downloaded."""


# ``Stocks-1Min-Price``, ``Cryptocurrencies-1Min-Price``, ``Forex-1Min-Price``...
_MINUTE_DATASET = re.compile(r"-1min-", re.IGNORECASE)


def is_minute_dataset(path) -> bool:
    """True for the 1-minute bar datasets, stored as one parquet shard per month."""
    return bool(_MINUTE_DATASET.search(str(path).strip().rsplit("/", 1)[-1]))


def _warn_unbounded_minute(name: str, symbols) -> None:
    price = "adj_close" if name.lower().startswith("stocks-") else "close"
    scope = "every month" if symbols is not None else "every month of every symbol"
    warnings.warn(
        f"{name} is stored as one shard per month (Stocks-1Min-Price is ~75 GB): without "
        f"start/end, load_dataset downloads {scope} before returning. Bound the read so only "
        f"the months you need are downloaded, e.g. load_dataset({name!r}, symbols=['SPY'], "
        f"start='2024-01-01', end='2024-03-31', columns=[{price!r}, 'volume']).",
        UnboundedMinuteLoadWarning,
        stacklevel=3,
    )


def load_dataset(
    path,
    symbols=None,
    adjust=True,
    extend=False,
    to_usd=True,
    rate_to_price=True,
    use_hf=False,
    start=None,
    end=None,
    columns=None,
):
    """Load a PWB dataset as a pandas DataFrame.

    Parameters
    ----------
    path : str
        Dataset name, e.g. ``"Stocks-Daily-Price"`` or ``"Stocks-1Min-Price"``.
    symbols : str or list of str, optional
        Keep only these symbols. The filter is pushed down to each shard's
        read, so memory stays bounded to the matching rows. Universe names
        (``"sp500"``...) are resolved as before.
    adjust, extend, to_usd, rate_to_price : bool
        Post-processing of the daily price datasets, unchanged.
    use_hf : bool
        Read from the Hugging Face Hub even when ``PWB_API_KEY`` is set.
    start, end : date-like, optional
        Inclusive window on the ``datetime`` column (the ``date`` column when
        there is none). Only the shards whose period intersects the window
        are downloaded -- a minute dataset is one shard per month -- and rows
        outside it are dropped inside the parquet read. A bare date covers the
        whole day: ``end="2024-03-31"`` keeps every bar of 31 March. A bound
        with a time (``"2024-03-15 09:30"``) is compared with the stored naive
        timestamps as written.
    columns : list of str, optional
        Read only these columns, plus the keys the table has (``symbol``,
        ``date``/``datetime``). For the minute datasets the read never
        materialises the other columns. An unknown column is an error.

    Without ``start``, ``end`` and ``columns`` the behaviour is unchanged. A
    minute dataset loaded without ``start``/``end`` still loads, but warns
    (``UnboundedMinuteLoadWarning``): it downloads every month, ~75 GB for
    ``Stocks-1Min-Price``. An intraday strategy should bound its read::

        bars = load_dataset("Stocks-1Min-Price", symbols=["SPY", "QQQ"],
                            start="2024-01-01", end="2024-03-31",
                            columns=["adj_open", "adj_close", "volume"])
    """
    if str(path).strip().rsplit("/", 1)[-1].lower() == "options-daily-price":
        # ~560 M rows, ~20 GB: this function downloads every shard before it
        # filters, which is how Stocks-1Min-Price filled a disk on 2026-11-05.
        # Compared without case: the Hub resolves "options-daily-price" to the
        # same repository, and an exact match let that spelling through.
        raise ValueError(
            "Options-Daily-Price is not loaded whole: use "
            "pwb_toolbox.datasets.load_option_chain(underlyings, start, end, columns=...), "
            "which downloads only the chains and months asked for."
        )

    split = "train"
    pwb_api_key = _get_pwb_api_key()

    if isinstance(columns, str):
        columns = [columns]
    if columns is not None:
        columns = list(columns)
    # The shards ``get_pricing`` picked for this read, if it is one of its
    # own (see ``_pricing_shard_window``). Consumed here, so that a load made
    # from inside this one -- the forex table behind ``to_usd``, the proxies
    # behind ``extend`` -- reads every shard as before.
    shard_window = _SHARD_WINDOW.get()
    if shard_window is not None:
        _SHARD_WINDOW.set(None)
    window = _Window(start, end) if start is not None or end is not None else None
    if window is None and is_minute_dataset(path):
        _warn_unbounded_minute(str(path).strip().rsplit("/", 1)[-1], symbols)
    # The daily price tables are post-processed below (adjustment, currency,
    # direction of forex pairs) from their full set of price columns, so
    # ``columns`` selects among the result instead of the read.
    read_columns = None if path in DAILY_PRICE_DATASETS else columns
    # Passed on only when asked for, so a loader replaced in a test or a
    # wrapper keeps the signature it has always had.
    bounds = {}
    if read_columns is not None:
        bounds["columns"] = read_columns
    if window is not None:
        bounds["window"] = window
        shard_window = None

    # Resolve the symbol filter up front (on a copy, so the caller's list is
    # never mutated) so it can be pushed down to the per-shard parquet reads
    # instead of concatenating every shard in memory and filtering afterwards.
    if isinstance(symbols, str):
        symbols = [symbols]  # 29 callers pass the bare string, so honour it

    symbol_filter = None
    pit_top_n = None
    pit_only = None
    if isinstance(symbols, list):
        symbol_filter, pit_top_n, pit_added, explicit = _resolve_universe(symbols)
        pit_only = pit_added - explicit

    # A forex pair is read under both spellings: the table keeps one per pair
    # and the caller may name the other (see _forex_resolve_directions).
    read_filter = symbol_filter
    if path == FOREX_DAILY_DATASET:
        read_filter = _forex_widen_filter(symbol_filter)

    # The shard window reaches the loader through a context variable rather
    # than an argument, for the same reason as ``bounds``; a loader that
    # ignores it reads every shard, and ``get_pricing`` cuts the dates anyway.
    loader_token = _LOADER_SHARD_WINDOW.set(shard_window)
    try:
        if pwb_api_key and not use_hf:
            df = _load_dataset_from_pwb(path, split=split, pwb_api_key=pwb_api_key, symbols=read_filter, **bounds)
        else:
            hf_token = os.getenv("HF_ACCESS_TOKEN")
            if not hf_token:
                raise ValueError("Set PWB_API_KEY or HF_ACCESS_TOKEN to load datasets.")
            df = _load_dataset_from_hf(path, split=split, hf_token=hf_token, symbols=read_filter, **bounds)
    finally:
        _LOADER_SHARD_WINDOW.reset(loader_token)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])

    # Safety net: the reads above already push the symbol filter down, but keep a
    # post-filter so the result is identical regardless of the shard column layout.
    if read_filter is not None:
        if "symbol" in df.columns:
            df = df[df["symbol"].isin(read_filter)].copy()
        if "symbols" in df.columns:
            symbol_set = set(read_filter)
            df = df[
                df["symbols"].apply(lambda cell: _symbols_overlap(cell, symbol_set))
            ].copy()

    # The load above widened to every name that ever belonged to the universe.
    # This is the pass that keeps each one to the dates it actually belonged;
    # the names the caller asked for by itself are not its business.
    if pit_top_n is not None:
        from .pit_universe import apply_pit_membership

        df = apply_pit_membership(df, *pit_top_n, only=pit_only)

    if path == FOREX_DAILY_DATASET:
        df = _forex_resolve_directions(df, symbol_filter, to_usd=to_usd)

    if path == "Universe-Daily-Price":
        df = _with_forex_inverse_names(df)

    if path in DAILY_PRICE_DATASETS:
        if adjust and "adj_close" in df.columns:
            adj_factor = df["adj_close"] / df["close"]
            df["adj_open"] = df["open"] * adj_factor
            df["adj_high"] = df["high"] * adj_factor
            df["adj_low"] = df["low"] * adj_factor
            df.drop(columns=["open", "high", "low", "close"], inplace=True)
            df.rename(
                columns={
                    "adj_open": "open",
                    "adj_high": "high",
                    "adj_low": "low",
                    "adj_close": "close",
                },
                inplace=True,
            )
        else:
            if "adj_close" in df.columns:
                df.drop(columns=["adj_close"])

    if path in DAILY_PRICE_DATASETS and (extend and path == "ETFs-Daily-Price"):
        df = __extend_etfs(df)

    if path in DAILY_PRICE_DATASETS and to_usd:
        if path == FOREX_DAILY_DATASET:
            df = _forex_to_usd(df)
        elif path == "Indices-Daily-Price":
            df_forex = load_dataset("Forex-Daily-Price", to_usd=True)
            df = __convert_indices_to_usd(df, df_forex)

    if path in DAILY_PRICE_DATASETS and rate_to_price and path == "Bonds-Daily-Price":
        df = __convert_bond_rates_to_prices(df)

    if columns is not None and read_columns is None:
        unknown = [c for c in columns if c not in df.columns]
        if unknown:
            raise ValueError(f"unknown columns {unknown}; the dataset has {list(df.columns)}")
        keys = [c for c in _KEY_COLUMNS if c in df.columns]
        df = df[list(dict.fromkeys(keys + columns))]

    return df


def __convert_indices_to_usd(
    df_indices: pd.DataFrame, df_forex: pd.DataFrame
) -> pd.DataFrame:
    mapping = {
        "ADSMI": "AED",  # United Arab Emirates
        "AEX": "EUR",  # Netherlands
        "AS30": "AUD",  # Australia
        "AS51": "AUD",  # Australia
        "AS52": "AUD",  # Australia
        "ASE": "EUR",  # Greece
        "ATX": "EUR",  # Austria
        "BEL20": "EUR",  # Belgium
        "BELEX15": "RSD",  # Serbia
        "BGSMDC": "BWP",  # Botswana
        "BHSEEI": "BHD",  # Bahrain
        "BKA": "BAM",  # Bosnia and Herzegovina
        "BLOM": "LBP",  # Lebanon
        "BSX": "BMD",  # Bermuda
        "BUX": "HUF",  # Hungary
        "BVLX": "BOB",  # Bolivia
        "BVPSBVPS": "PAB",  # Panama
        "BVQA": "USD",  # Ecuador
        "CAC": "EUR",  # France
        "CASE": "EGP",  # Egypt
        "CCMP": "USD",  # United States
        "COLCAP": "COP",  # Colombia
        "CRSMBCT": "CRC",  # Costa Rica
        "CSEALL": "LKR",  # Sri Lanka
        "CYSMMAPA": "EUR",  # Cyprus
        "DARSDSEI": "TZS",  # Tanzania
        "DAX": "EUR",  # Germany
        "DFMGI": "AED",  # United Arab Emirates
        "DSEX": "BDT",  # Bangladesh
        "DSM": "QAR",  # Qatar
        "ECU": "USD",  # Ecuador
        "FBMKLCI": "MYR",  # Malaysia
        "FSSTI": "SGD",  # Singapore
        "FTN098": "NAD",  # Namibia
        "FTSEMIB": "EUR",  # Italy
        "GGSECI": "GHS",  # Ghana
        "HEX": "EUR",  # Finland
        "HEX25": "EUR",  # Finland
        "HSI": "HKD",  # Hong Kong
        "IBEX": "EUR",  # Spain
        "IBOV": "BRL",  # Brazil
        "IBVC": "VES",  # Venezuela
        "ICEXI": "ISK",  # Iceland
        "IGPA": "CLP",  # Chile
        "INDEXCF": "RUB",  # Russia
        "INDU": "USD",  # United States
        "INDZI": "IDR",  # Indonesia
        "ISEQ": "EUR",  # Ireland
        "JALSH": "ZAR",  # South Africa
        "JCI": "IDR",  # Indonesia
        "JMSMX": "JMD",  # Jamaica
        "JOSMGNFF": "JOD",  # Jordan
        "KFX": "DKK",  # Denmark
        "KNSMIDX": "KES",  # Kenya
        "KSE100": "PKR",  # Pakistan
        "KZKAK": "KZT",  # Kazakhstan
        "LSXC": "LAK",  # Laos
        "LUXXX": "EUR",  # Luxembourg
        "MALTEX": "EUR",  # Malta
        "MBI": "MKD",  # North Macedonia
        "MERVAL": "ARS",  # Argentina
        "MEXBOL": "MXN",  # Mexico
        "MONEX": "EUR",  # Montenegro
        "MOSENEW": "MAD",  # Morocco
        "MSETOP": "MKD",  # North Macedonia
        "MSM30": "OMR",  # Oman
        "NDX": "USD",  # United States
        "NGSEINDX": "NGN",  # Nigeria
        "NIFTY": "INR",  # India
        "NKY": "JPY",  # Japan
        "NSEASI": "KES",  # Kenya
        "NZSE50FG": "NZD",  # New Zealand
        "OMX": "SEK",  # Sweden
        "OSEAX": "NOK",  # Norway
        "PCOMP": "PHP",  # Philippines
        "PFTS": "UAH",  # Ukraine
        "PSI20": "EUR",  # Portugal
        "PX": "CZK",  # Czech Republic
        "RIGSE": "EUR",  # Latvia
        "RTY": "USD",  # United States
        "SASEIDX": "SAR",  # Saudi Arabia
        "SASX10": "BAM",  # Bosnia and Herzegovina
        "SBITOP": "EUR",  # Slovenia
        "SEMDEX": "MUR",  # Mauritius
        "SENSEX": "INR",  # India
        "SET50": "THB",  # Thailand
        "SHCOMP": "CNY",  # China
        "SHSZ300": "CNY",  # China
        "SKSM": "EUR",  # Slovakia
        "SMI": "CHF",  # Switzerland
        "SOFIX": "BGN",  # Bulgaria
        "SPBLPGPT": "PEN",  # Peru
        "SPTSX": "CAD",  # Canada
        "SPX": "USD",  # United States
        "SSE50": "CNY",  # China
        "SX5E": "EUR",  # Europe
        "TA125": "ILS",  # Israel
    }
    frames = []

    # iterate over the symbols that actually exist in df_indices
    for symbol in df_indices["symbol"].unique():
        df_idx = df_indices[df_indices["symbol"] == symbol].copy()

        # 1) Figure out what currency the index is quoted in.
        ccy = mapping.get(symbol)  # None if not mapped
        if ccy is None or ccy == "USD":
            # Unknown or already USD – just keep the original rows
            frames.append(df_idx)
            continue

        # 2) Find the matching FX rate (home-ccy → USD)
        pair = ccy + "USD"
        df_fx = df_forex[df_forex["symbol"] == pair].copy()

        if df_idx.empty or df_fx.empty:
            # No FX data – keep raw index levels instead of dropping them
            frames.append(df_idx)
            continue

        # 3) Merge on date and convert OHLC
        merged = pd.merge(df_idx, df_fx, on="date", suffixes=("", "_fx"))
        for col in ("open", "high", "low", "close"):
            merged[col] = merged[col] * merged[f"{col}_fx"]

        frames.append(merged[["symbol", "date", "open", "high", "low", "close"]])

    if not frames:
        return pd.DataFrame(columns=df_indices.columns)

    # Combine everything back into one DataFrame
    return pd.concat(frames, ignore_index=True)


def __convert_bond_rates_to_prices(df: pd.DataFrame, face_value: float = 100.0) -> pd.DataFrame:
    """
    Convert bond yields (in percent) to prices, in-place, for rows whose
    symbols encode maturity like 'US10Y', 'US2Y', 'US3M', etc.

    Assumes columns: ['symbol', 'open', 'high', 'low', 'close'] and that
    open/high/low/close are yields in percent.
    """
    # Vectorized extraction of maturity from symbol: last part "10Y", "2Y", "3M", ...
    m = df["symbol"].str.extract(r"(\d+)([YM])$")  # 0: number, 1: unit
    num = pd.to_numeric(m[0], errors="coerce")
    unit = m[1]

    years = pd.Series(np.nan, index=df.index, dtype="float64")
    years[unit == "Y"] = num[unit == "Y"]
    years[unit == "M"] = num[unit == "M"] / 12.0

    # Only apply to rows where we successfully parsed the maturity
    mask = years.notna()
    if not mask.any():
        return df

    y = years[mask]

    # Vectorized rate->price for each OHLC column
    for col in ["open", "high", "low", "close"]:
        r = df.loc[mask, col] / 100.0  # percent -> fraction
        df.loc[mask, col] = face_value / (1.0 + r) ** y

    return df


#: ``{ETF: [dataset, proxy]}``: the history ``extend=True`` splices in front of
#: an ETF, scaled to its first common close (see ``__extend_etfs``).
_ETF_PROXIES = {
        "AGG": ["Bonds-Daily-Price", "US10Y"],
        "EPP": ["Indices-Daily-Price", "HSI"],
        "EWA": ["Indices-Daily-Price", "AS30"],  # Australia
        "EWO": ["Indices-Daily-Price", "ATX"],  # Austria
        "EWK": ["Indices-Daily-Price", "BEL20"],  # Belgium
        "EWZ": ["Indices-Daily-Price", "IBOV"],  # Brazil
        "EWC": ["Indices-Daily-Price", "SPTSX"],  # Canada
        "FXI": ["Indices-Daily-Price", "SSE50"],  # China
        "EWQ": ["Indices-Daily-Price", "CAC"],  # France
        "EWG": ["Indices-Daily-Price", "DAX"],  # Germany
        "EWH": ["Indices-Daily-Price", "HSI"],  # Hong Kong
        "EWI": ["Indices-Daily-Price", "FTSEMIB"],  # Italy
        "EWJ": ["Indices-Daily-Price", "NKY"],
        "EWM": ["Indices-Daily-Price", "FBMKLCI"],  # Malaysia
        "EWW": ["Indices-Daily-Price", "MEXBOL"],  # Mexico
        "EWN": ["Indices-Daily-Price", "AEX"],  # Netherlands
        "EWS": ["Indices-Daily-Price", "FSSTI"],  # Singapore
        "EZA": ["Indices-Daily-Price", "TOP40"],  # South Africa
        "EWP": ["Indices-Daily-Price", "IBEX"],  # Spain
        "EWD": ["Indices-Daily-Price", "OMX"],  # Sweden
        "EWL": ["Indices-Daily-Price", "SMI"],  # Switzerland
        "EWT": ["Indices-Daily-Price", "TWSE"],  # Taiwan
        "EWU": ["Indices-Daily-Price", "UKX"],  # United Kingdom
        "GLD": ["Commodities-Daily-Price", "GC1"],
        "GSG": ["Commodities-Daily-Price", "GC1"],
        "IEF": ["Bonds-Daily-Price", "US10Y"],
        "IEV": ["Indices-Daily-Price", "SX5E"],
        "IWB": ["Indices-Daily-Price", "SPX"],
        "QQQ": ["Indices-Daily-Price", "NDX"],
        "SHY": ["Bonds-Daily-Price", "US1Y"],
        "SPY": ["Indices-Daily-Price", "SPX"],
        "THD": ["Indices-Daily-Price", "SET50"],  # Thailand
        "USO": ["Commodities-Daily-Price", "CL1"],
}


def __extend_etfs(df_etfs):

    mapping = _ETF_PROXIES
    symbols = df_etfs.symbol.unique()
    mapping = {k: v for k, v in mapping.items() if k in symbols}

    # Nothing to extend → just return the input
    if not mapping:
        return df_etfs.copy()

    # ------------------------------------------------------------------ step 2
    grouped = defaultdict(list)  # {path: [proxy1, proxy2, ...]}
    for _, (path, proxy) in mapping.items():
        grouped[path].append(proxy)

    # Load each dataset only if there's at least one proxy symbol
    other_frames = []
    for path, proxies in grouped.items():
        if proxies:  # skip empty lists
            other_frames.append(load_dataset(path, proxies, to_usd=True))

    # If no proxy data could be loaded, fall back to raw ETF data
    if not other_frames:
        return df_etfs.copy()

    df_others = pd.concat(other_frames, ignore_index=True)

    # ------------------------------------------------------------------ step 3
    frames = []
    for etf, (__, proxy) in mapping.items():
        etf_data = df_etfs[df_etfs["symbol"] == etf]
        proxy_data = df_others[df_others["symbol"] == proxy]

        if etf_data.empty or proxy_data.empty:
            frames.append(etf_data)  # keep raw ETF if proxy missing
            continue

        # Find first overlapping date
        first_common = etf_data.loc[
            etf_data["date"].isin(proxy_data["date"]), "date"
        ].min()
        if pd.isna(first_common):
            frames.append(etf_data)  # no overlap → keep raw ETF
            continue

        # Compute adjustment factor on that date
        k = (
            etf_data.loc[etf_data["date"] == first_common, "close"].iloc[0]
            / proxy_data.loc[proxy_data["date"] == first_common, "close"].iloc[0]
        )

        # Scale proxy history before the overlap
        hist = proxy_data[proxy_data["date"] < first_common].copy()
        hist[["open", "high", "low", "close"]] *= k
        hist["symbol"] = etf

        # Combine proxy history + actual ETF data
        frames.append(pd.concat([hist, etf_data]))

    # Add ETFs that were never in the mapping
    untouched = set(symbols) - set(mapping)
    frames.append(df_etfs[df_etfs["symbol"].isin(untouched)])

    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )


ALLOWED_FIELDS = {"open", "high", "low", "close", "volume"}


# Which repository a bare ticker resolves to when ``Universe-Daily-Price`` lists
# it in several, first match wins. ``Universe-Daily-Price`` carries one row per
# (symbol, repo_id) and no preference, and until 2026-10-18 the reader took the
# last row -- which is ``Stocks-Daily-Price`` by alphabetical accident. That was
# harmless while the stock feed held stocks only. Since the Massive merge of
# 2026-10-11 it also holds every US-listed ETF and the 2024-25 crypto ETFs, so
# the index regenerated on 2026-10-17 sent 6 229 bare tickers to the stock feed:
# 5 155 ETFs, 1 058 crypto. Measured on the published strategies: 816 of them
# name a bare ETF ticker -- SPY 484, TLT 128, IEF 123, GLD 105, IWM 104, QQQ 92 --
# and for each the series now started on 2003-09-10 (the first Massive session)
# instead of 1993 for SPY, 1999 for QQQ, 2002 for TLT, and ``__extend_etfs``'
# proxies (SPY <- SPX, GLD <- GC1 ...) no longer applied, since they act on the
# ETF feed alone.
#
# The ETF feed goes first: it holds nothing but ETFs, is adjusted for total
# return, and is the longer history. Stocks stay ahead of everything else, which
# is what the last-row rule always did: a ticker that is both a stock and a
# coin -- ABT, CAKE, STX, LTC, DASH, SOL, LINK -- is used as the stock by 583
# published strategies against 463 crypto-themed ones, and the ``.CRP``,
# ``.IDX`` suffixes exist for the rest.
#
# The three repositories at the tail hold what the US equity feed used to mix
# into ``Stocks-Daily-Price`` -- preferred shares, warrants / rights / units,
# and structured products (ETNs excepted, which stay ETFs) -- sorted upstream
# by instrument type since the split of 2026-11. A ticker that changed class
# over its life (a SPAC unit that became a common stock, a preferred whose
# ticker was later reused) can sit in two of these feeds at once; the stock
# reading wins, which is also what an untyped symbol defaults to upstream.
_BARE_SYMBOL_PRIORITY = (
    "ETFs-Daily-Price",
    "Stocks-Daily-Price",
    "Indices-Daily-Price",
    "Cryptocurrencies-Daily-Price",
    "Bonds-Daily-Price",
    "Commodities-Daily-Price",
    "Forex-Daily-Price",
    "Preferreds-Daily-Price",
    "Warrants-Daily-Price",
    "StructuredProducts-Daily-Price",
)


def _bare_symbol_routes(universe: pd.DataFrame) -> dict:
    """``{symbol: repo_id}`` from the index, one repository per bare ticker.

    Ties are broken by ``_BARE_SYMBOL_PRIORITY``; a repository the list does
    not know sorts after every one it does, so a new feed cannot silently
    capture a ticker.
    """
    rank = {name: i for i, name in enumerate(_BARE_SYMBOL_PRIORITY)}
    frame = universe[["symbol", "repo_id"]].dropna().copy()
    frame["_rank"] = [
        rank.get(str(r).split("/")[-1], len(rank)) for r in frame["repo_id"]
    ]
    frame = frame.sort_values(["symbol", "_rank"], kind="stable")
    frame = frame.drop_duplicates("symbol", keep="first")
    return dict(zip(frame["symbol"], frame["repo_id"]))


# A ticker that both the ETF feed and the stock feed carry is not settled by
# the priority above: the index regenerated on 2026-11-02 lists 1 459 of them,
# and since that day the ETF reading has won every one. For 878 the two feeds
# hold the same series (an ETF the stock feed still carries), so the choice is
# moot. The rest are a ticker reused by two instruments, and "ETF first" then
# hands a strategy a fund it never asked for: bare ``META`` -- named in 518
# published strategies, rank 4 of the liquid universe since 2022 -- became a
# thematic ETF quoted 148 sessions in 2021-22 at 12-15 dollars, in place of
# the stock quoted since 2012; ``BNY``, ``CALY``, ``FB``, ``TOT`` likewise.
# Swapping the order would only move the error to ``HYG``, ``GDX``, ``VEA``,
# live ETFs whose ticker a stock carried for a few weeks in 2003-04.
#
# So between these two feeds the series that covers the requested window wins:
# the most sessions between ``start_date`` and ``end_date``, a tie going to the
# priority above. A name the point-in-time universe brought in never reaches
# this point: the universe is built from US common stocks.
_ARBITRATED_REPOS = ("ETFs-Daily-Price", "Stocks-Daily-Price")

# Two feeds of one ticker quote one instrument when they trade on the same
# sessions -- nine in ten of the sessions either carries -- or, failing that,
# when their closes agree where they meet (a median gap under 2 % in log
# terms). The session test is the one that matters: 862 of the 1 459 pairs are
# a fund the stock feed still carries, and 18 of them differ by a split or
# total-return adjustment that the price test alone would read as two
# instruments. A reused ticker does not share sessions: ``BNY`` the fund and
# ``BNY`` the bank overlap on 6 170 of 13 480 sessions, ``META`` on 148 of 3 627.
_SAME_SERIES_SESSIONS = 0.9
_SAME_SERIES_LOG_GAP = 0.02
# One instrument in both feeds: the ETF copy is kept while it has at least this
# share of the stock copy's sessions in the window. The stock feed routinely
# runs a few sessions past the ETF feed; that alone must not move a fund.
_SAME_SERIES_COVERAGE = 0.95


def _arbitrated_symbols(universe: pd.DataFrame) -> frozenset:
    """Bare tickers the index lists under every repository of ``_ARBITRATED_REPOS``."""
    frame = universe[["symbol", "repo_id"]].dropna()
    repos = frame["repo_id"].astype(str).str.split("/").str[-1]
    frame = frame[repos.isin(_ARBITRATED_REPOS)]
    counts = frame.drop_duplicates().groupby("symbol")["repo_id"].nunique()
    return frozenset(counts[counts >= len(_ARBITRATED_REPOS)].index.astype(str))


def _same_series(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """True when two feeds of one ticker quote the same instrument."""
    left = a.drop_duplicates("date").set_index("date")["close"]
    right = b.drop_duplicates("date").set_index("date")["close"]
    union = left.index.union(right.index)
    common = left.index.intersection(right.index)
    if len(union) and len(common) / len(union) >= _SAME_SERIES_SESSIONS:
        return True
    both = pd.concat([left, right], axis=1, join="inner").dropna()
    both = both[(both.iloc[:, 0] > 0) & (both.iloc[:, 1] > 0)]
    if both.empty:
        return False
    gap = np.abs(np.log(both.iloc[:, 0].astype(float) / both.iloc[:, 1].astype(float)))
    return bool(np.median(gap) < _SAME_SERIES_LOG_GAP)


def _arbitrate_collisions(frames: dict, contested, start_date, end_date) -> dict:
    """Keep, for each contested ticker, the one feed that covers the window.

    ``frames`` maps a repository name to its loaded long frame. Every contested
    ticker was loaded from each repository of ``_ARBITRATED_REPOS``; the rows
    of the losing feed are dropped here, before the frames are concatenated
    (two feeds under one name would otherwise be averaged by the pivot).
    Returns the frames, filtered.
    """
    if not contested:
        return frames
    # ``None`` leaves that side of the window open, as ``df.loc[None:None]``
    # does below; ``pd.Timestamp(None)`` is NaT, which no session is between,
    # and would hand every collision to the ETF feed on a 0-0 tie.
    start = pd.Timestamp.min if start_date is None else pd.Timestamp(start_date)
    end = pd.Timestamp.max if end_date is None else pd.Timestamp(end_date)
    rank = {name: i for i, name in enumerate(_BARE_SYMBOL_PRIORITY)}
    drop = {repo: set() for repo in frames}
    for sym in sorted(contested):
        parts = {}
        for repo in _ARBITRATED_REPOS:
            frame = frames.get(repo)
            if frame is None or frame.empty:
                continue
            rows = frame[frame["symbol"].astype(str) == sym]
            if not rows.empty:
                rows = rows.assign(date=pd.to_datetime(rows["date"]))
                parts[repo] = rows
        if len(parts) < 2:
            continue  # only one feed has rows: nothing to choose
        etf, stock = (parts[repo] for repo in _ARBITRATED_REPOS)
        same = _same_series(etf, stock)
        sessions = {
            repo: int(rows["date"].between(start, end).sum()) for repo, rows in parts.items()
        }
        if same:
            # One fund in both feeds: the ETF feed's copy is the adjusted one,
            # and the one ``__extend_etfs`` extends -- as long as it covers the
            # window. 64 of the pairs are a closed-end fund or a REIT that the
            # ETF feed only carries from 2020-22 while the stock feed has it
            # since 1980-2006 (DHC, named in 23 strategies, NXDT, STEW, BRW):
            # the ETF copy would cut decades off the history.
            etf_repo, stock_repo = _ARBITRATED_REPOS
            if sessions[etf_repo] >= _SAME_SERIES_COVERAGE * sessions[stock_repo]:
                winner = etf_repo
            else:
                winner = stock_repo
        else:
            winner = min(parts, key=lambda repo: (-sessions[repo], rank.get(repo, len(rank))))
        for repo in parts:
            if repo != winner:
                drop[repo].add(sym)
        loser = next(repo for repo in parts if repo != winner)
        if sessions[loser] and not same:
            kind = {"ETFs-Daily-Price": "ETF", "Stocks-Daily-Price": "STK"}
            print(
                f"Warning: '{sym}' names two instruments in the window: "
                f"{winner} ({sessions[winner]} sessions, used) and "
                f"{loser} ({sessions[loser]} sessions, ignored). "
                f"Pass '{sym}.{kind[loser]}' for the other one, "
                f"or '{sym}.{kind[winner]}' to make this choice explicit."
            )
    out = {}
    for repo, frame in frames.items():
        if drop.get(repo):
            frame = frame[~frame["symbol"].astype(str).isin(drop[repo])]
        out[repo] = frame
    return out


# A reused ticker is published one instrument per name since the price sort of
# 2026-11 (data-api #55): the instrument that traded under the ticker last
# keeps it bare, each earlier one is ``<TICKER>_<YYYYMMDD>`` -- the last day it
# traded under the ticker (``ASO`` is Academy Sports since 2020,
# ``ASO_20061103`` AmSouth Bancorporation). A strategy written before that
# names the bare ticker for the instrument of its own window: ``FB`` for
# Facebook in 2015 would otherwise load the buffer ETF that took the ticker in
# 2025 -- no row in the window, and no error. So a bare ticker is resolved by
# window: of the instruments that traded under it, the one with the most
# sessions in [start_date, end_date] is loaded, under the bare name the
# strategy asked for, with a warning naming it. Two instruments are never
# stitched together; naming a dated symbol explicitly bypasses all of this.
_DATED_NAME = re.compile(r"^(?P<ticker>.+)_(?P<day>\d{8})$")


def _dated_names(universe: pd.DataFrame) -> dict:
    """``{bare ticker: [dated names]}`` from the index."""
    out = defaultdict(set)
    for sym in universe["symbol"].dropna().astype(str):
        match = _DATED_NAME.match(sym)
        if match:
            out[match.group("ticker")].add(sym)
    return {k: sorted(v) for k, v in out.items()}


def _resolve_reused_tickers(frames: dict, reused: dict, start_date, end_date) -> dict:
    """Keep, for each reused bare ticker, the one instrument that covers the window.

    ``reused`` maps the bare ticker to the names loaded for it (itself, when the
    index has it, and its dated names). The winner's rows are renamed to the
    bare ticker; the other candidates' rows are dropped.
    """
    if not reused:
        return frames
    start = pd.Timestamp.min if start_date is None else pd.Timestamp(start_date)
    end = pd.Timestamp.max if end_date is None else pd.Timestamp(end_date)
    for bare, names in reused.items():
        spans = {}
        for frame in frames.values():
            if frame is None or frame.empty:
                continue
            sym = frame["symbol"].astype(str)
            for name in names:
                rows = frame.loc[sym == name, "date"]
                if rows.empty:
                    continue
                days = pd.to_datetime(rows)
                spans[name] = (int(((days >= start) & (days <= end)).sum()),
                               days.min(), days.max())
        if not spans:
            continue
        best = max(spans, key=lambda n: (spans[n][0], n == bare, n))
        losers = [n for n in spans if n != best]
        for repo, frame in list(frames.items()):
            if frame is None or frame.empty:
                continue
            sym = frame["symbol"].astype(str)
            frame = frame[~sym.isin(losers)].copy()
            if best != bare:
                sym = frame["symbol"].astype(str)
                frame["symbol"] = sym.where(sym != best, bare)
            frames[repo] = frame
        if best != bare or any(spans[n][0] for n in losers):
            def describe(n):
                count, first, last = spans[n]
                return f"'{n}' ({first:%Y-%m-%d}..{last:%Y-%m-%d}, {count} sessions in the window)"
            others = "; ".join(describe(n) for n in losers) or "none"
            loaded_as = f", loaded as '{bare}'" if best != bare else ""
            print(
                f"Warning: '{bare}' named several instruments over time; for this window it "
                f"resolves to {describe(best)}{loaded_as}. Other instruments under '{bare}': "
                f"{others}. Instruments are never stitched; name one explicitly to choose it."
            )
    return frames


class _Routes(dict):
    """A read-only record carried in ``DataFrame.attrs``: copied by reference.

    pandas deep-copies ``attrs`` into the result of most operations; a strategy
    that runs a thousand of them on the panel should not copy two thousand
    routes each time.
    """

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


def _loaded_routes(grouped: dict, loaded: dict, resolved: set) -> dict:
    """``{symbol: repository}`` -- where each column of ``get_pricing`` was read from.

    ``grouped`` is the routing before the load; for the names whose feed is
    settled by the data itself (a ticker both the ETF and the stock feeds carry,
    a reused ticker) the repository that kept the rows answers instead.
    """
    routes = _Routes()
    for repo_id, names in grouped.items():
        for name in names:
            routes.setdefault(name, repo_id)
    for name in resolved:
        for repo_id, frame in loaded.items():
            if frame is not None and not frame.empty and (frame["symbol"] == name).any():
                routes[name] = repo_id
                break
    return routes


# --------------------------------------------------------------------------- #
# Shards ``get_pricing`` reads                                                #
# --------------------------------------------------------------------------- #
# ``get_pricing`` slices its panel to ``[start_date, end_date]`` and, until
# 0.1.50, read every shard to do it: the 779 monthly shards of
# ``Stocks-Daily-Price`` back to 1962 for a backtest starting in 1998 (456 of
# them before 2000), and the 587 of ``ETFs-Daily-Price`` back to 1978. It now
# reads only the shards whose month can hold a row of the window (one day of
# slack each side, as ``_Window.overlaps``), and keeps every row of those
# shards: the dates are still cut by the ``df.loc[start_date:end_date]`` below,
# so the rows that reach the panel are the ones they always were.
#
# Only where nothing before the cut reads the dates outside the window:
#
# * the two repositories stored as monthly shards (the others are one file);
# * not for a ticker both feeds carry (``_arbitrate_collisions`` compares the
#   two whole series) or a reused ticker (``_resolve_reused_tickers`` prints
#   each instrument's first and last date);
# * not for ``ETFs-Daily-Price`` with ``extend=True`` when a requested ETF has
#   a proxy: ``__extend_etfs`` scales the proxy at the ETF's first close.
#
# The forex table is a single file and its direction rule reads whole series;
# it is read in full, as are the loads made from inside ``load_dataset``.
_SHARD_WINDOW: ContextVar = ContextVar("pwb_shard_window", default=None)
_PRUNABLE_REPOS = ("Stocks-Daily-Price", "ETFs-Daily-Price")


def _pricing_shard_window(repo_id, names, extend, contested, reused_names, start_date, end_date):
    """The shard-picking window for one of ``get_pricing``'s loads, or ``None``."""
    if repo_id not in _PRUNABLE_REPOS or (start_date is None and end_date is None):
        return None
    if any(name in contested or name in reused_names for name in names):
        return None
    if repo_id == "ETFs-Daily-Price" and extend and any(name in _ETF_PROXIES for name in names):
        return None
    try:
        return _Window(start_date, end_date, rows=False)
    except ValueError:
        return None


def _load_for_pricing(repo_id, names, extend, shard_window):
    if shard_window is None:
        return load_dataset(repo_id, names, extend=extend)
    token = _SHARD_WINDOW.set(shard_window)
    try:
        return load_dataset(repo_id, names, extend=extend)
    finally:
        _SHARD_WINDOW.reset(token)


def get_pricing(
    symbol_list,
    fields=None,  # ← default set below
    start_date="1980-01-01",
    end_date=date.today().isoformat(),
    extend=False,
    keep_single_level=False,  # backward-compat flag
    pit_cut=True,
):
    """
    Fetch OHLC pricing for the requested symbols.

    Parameters
    ----------
    symbol_list : str | list[str]
        One ticker or a list of tickers. Supports suffixed form "SYM.CAT"
        where CAT in {CRYPTO, STOCK, CMDTY, IDX, ETF, FX, BND}.
    fields : list[str] | None
        Any subset of ["open", "high", "low", "close"].
        Defaults to ["close"] for backward compatibility.
    start_date, end_date : str (YYYY-MM-DD)
        Slice the date index (inclusive).
    extend : bool
        Pass-through to `load_dataset(..., extend=extend)`.
    keep_single_level : bool
        If `True` and only one field is requested, flatten the columns so the
        output matches the old behaviour (columns = symbols).  If `False`
        you always get a two-level MultiIndex `(symbol, field)`.
    pit_cut : bool
        With a point-in-time universe (``"sp500"``, ``"liquid1000"``), drop the
        rows of each name outside its membership (the default). ``False`` keeps
        every price row of every name that was ever a member: what
        ``run_strategy`` needs to value a position held through an exit at its
        real prices, membership being enforced on the orders instead.

    Returns
    -------
    pd.DataFrame
        * MultiIndex columns (symbol, field) when `len(fields) > 1`
        * Single-level columns     (symbol)      when one field & keep_single_level=True
    """
    if fields is None:
        fields = ["close"]
    if isinstance(symbol_list, str):
        symbol_list = [symbol_list]
    pit_top_n = None
    pit_added = frozenset()
    explicit = frozenset()
    if isinstance(symbol_list, list):
        # _resolve_universe copies, where the previous code mutated the
        # caller's list in place: a strategy that kept ``SYMS = ["sp500"]`` and
        # called twice lost the pseudo-symbol on the second call.
        symbol_list, pit_top_n, pit_added, explicit = _resolve_universe(symbol_list)

    fields = [f.lower() for f in fields]
    bad = [f for f in fields if f not in ALLOWED_FIELDS]
    if bad:
        raise ValueError(f"Invalid field(s): {bad}. Allowed: {sorted(ALLOWED_FIELDS)}")

    # --------------------------------------------------------------- download
    # Direct routing for suffixed symbols (skip Universe lookup)
    SUFFIX_TO_REPO = {
        "CRP": "paperswithbacktest/Cryptocurrencies-Daily-Price",
        "STK": "paperswithbacktest/Stocks-Daily-Price",
        "CMD": "paperswithbacktest/Commodities-Daily-Price",
        "IDX": "paperswithbacktest/Indices-Daily-Price",
        "ETF": "paperswithbacktest/ETFs-Daily-Price",
        "FXR": "paperswithbacktest/Forex-Daily-Price",
        "BND": "paperswithbacktest/Bonds-Daily-Price",
    }

    universe = load_dataset("Universe-Daily-Price")
    mapping = _bare_symbol_routes(universe)
    arbitrated = _arbitrated_symbols(universe)

    grouped = defaultdict(list)
    unmapped = []
    contested = set()
    dated = _dated_names(universe)
    requested = set(symbol_list)
    reused = {}

    def _reuse_candidates(bare, repo_filter=None):
        """Bare ticker plus its dated names, grouped by repository; False if none."""
        names = [n for n in dated.get(bare, []) if n not in requested]
        if not names:
            return False
        picked = []
        for name in [bare] + names:
            repo_full = mapping.get(name) if name != bare or repo_filter is None else repo_filter
            if not isinstance(repo_full, str):
                continue
            if repo_filter is not None and repo_full != repo_filter:
                continue
            grouped[repo_full.split("/")[1]].append(name)
            picked.append(name)
        if not picked:
            return False
        reused[bare] = picked
        return True

    for sym in symbol_list:
        # Case 1: suffixed like "BTC.CRYPTO" → route directly, use base symbol for the dataset
        if "." in sym:
            base, cat = sym.rsplit(".", 1)
            repo_full = SUFFIX_TO_REPO.get(cat.upper())
            if repo_full and _reuse_candidates(base, repo_full):
                continue  # resolved by window within that repository
            if repo_full:
                repo_id = repo_full.split("/")[1]  # dataset name only
                grouped[repo_id].append(base)  # dataset expects base ticker
                continue
            # unknown suffix → fall back to Universe mapping on the full symbol

        # Case 2: a name the point-in-time universe brought in. The universe
        # is built from US common stocks, so it is one, whatever else the
        # index lists under the same ticker: routed by the index, ``META``
        # became an ETF of 2021-22 on 2026-11-02 and left every "sp500"
        # backtest from its first session in the universe.
        if sym in pit_added and sym not in explicit:
            grouped["Stocks-Daily-Price"].append(sym)
            continue

        # Case 3: a ticker both the ETF and the stock feeds carry -- load
        # both, keep the one covering the window (_arbitrate_collisions).
        if sym in arbitrated:
            for repo_id in _ARBITRATED_REPOS:
                grouped[repo_id].append(sym)
            contested.add(sym)
            continue

        # Case 4: normal symbol → use Universe mapping; a reused ticker is
        # resolved by window among the instruments that traded under it.
        if _reuse_candidates(sym):
            continue
        repo_full = mapping.get(sym)
        repo_id = repo_full.split("/")[1] if isinstance(repo_full, str) else None
        if repo_id:
            grouped[repo_id].append(sym)
        elif sym in pit_added:
            # Universe-Daily-Price is stale with respect to the merged price
            # dataset and misses the delisted names -- which are exactly the
            # ones the survivorship fix exists to bring back. The universe is
            # built from US common stocks, so route there without the index.
            grouped["Stocks-Daily-Price"].append(sym)
        else:
            print(f"Warning: No dataset found for symbol '{sym}'")
            unmapped.append(sym)

    loaded = {}
    pruned = []
    reused_names = {name for names in reused.values() for name in names}
    for repo_id, syms in grouped.items():
        ext_flag = extend if repo_id != "Indices-Daily-Price" else False
        names = list(dict.fromkeys(syms))
        shard_window = _pricing_shard_window(
            repo_id, names, ext_flag, contested, reused_names, start_date, end_date
        )
        df_part = _load_for_pricing(repo_id, names, ext_flag, shard_window)
        if shard_window is not None:
            pruned.append((repo_id, names, ext_flag))
        if not df_part.empty:
            loaded[repo_id] = df_part
    if pruned and not loaded:
        # Nothing in the window anywhere: read everything, as before, so the
        # panel comes out the way it always did for an empty window.
        for repo_id, names, ext_flag in pruned:
            df_part = load_dataset(repo_id, names, extend=ext_flag)
            if not df_part.empty:
                loaded[repo_id] = df_part
    loaded = _arbitrate_collisions(loaded, contested, start_date, end_date)
    loaded = _resolve_reused_tickers(loaded, reused, start_date, end_date)
    routes = _loaded_routes(grouped, loaded, contested | set(reused))
    frames = [frame for frame in loaded.values() if not frame.empty]

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # The per-repo loads above were given concrete symbols, so load_dataset
    # never saw the pseudo-symbol and could not filter per date. Do it here,
    # while the frame is still long: after the pivot, membership would have to
    # be expressed as a mask over a (date, symbol) grid.
    if pit_top_n is not None and pit_cut and not df.empty:
        from .pit_universe import apply_pit_membership

        # Only the names the universe brought in: a hedge or benchmark named
        # by the caller next to "sp500" stays on every date.
        df = apply_pit_membership(df, *pit_top_n, only=pit_added - explicit)

    df["date"] = pd.to_datetime(df["date"])
    if pit_top_n is not None and not pit_cut and not df.empty:
        # Uncut, the panel still starts with the table: before its first
        # session no name is a member, and the cut would have left no row.
        # Without this a "sp500" backtest silently gained 1990-2003.
        from .pit_universe import load_pit_universe

        first = load_pit_universe(*pit_top_n)["date"].min()
        early = df["symbol"].astype(str).isin(pit_added - explicit) & (df["date"] < first)
        df = df[~early]
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    df = df.loc[start_date:end_date]

    # ------------------------------------------------------------- reshape
    prices = df.pivot_table(values=fields, index=df.index, columns="symbol")
    prices = prices.swaplevel(axis=1).sort_index(axis=1)

    if keep_single_level:
        if isinstance(prices.columns, pd.MultiIndex):
            prices.columns = [
                col if not isinstance(col, tuple) else col[-1] for col in prices.columns
            ]

    # Which feed each column came from, for the harness's checks: a bare
    # ticker's class (stock, ETF, index...) is decided here and nowhere else.
    prices.attrs["pwb_routes"] = routes
    return prices


from .options import OPTIONS_DAILY_DATASET, load_option_chain  # noqa: E402  (needs _hub_snapshot above)
