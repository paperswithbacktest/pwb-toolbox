"""Kenneth R. French's Data Library, downloaded on the user's machine.

The library (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
publishes the Fama-French factors, the momentum and reversal factors, the
industry portfolios and the sorted portfolios as zipped CSV files.

**Licence.** The data are Eugene F. Fama's and Kenneth R. French's. Their page
grants no redistribution right, so Papers With Backtest does not copy them
anywhere: nothing is on the Hub or behind the PWB API. This module downloads
the official zip from the author's site, on the user's machine, and keeps a
local copy. Cite the library in anything built on it.

**Point in time: there is none.** The library is recomputed from the current
CRSP and Compustat files at every update (about monthly), and the *whole*
history moves with it: a value-weighted industry return of 1963 read today is
not the one read a year ago. The site serves only the latest computation, so
no historical vintage can be loaded. What this module gives instead is the
date of the download (``df.attrs["downloaded_at"]``) and the CRSP vintage the
file says it was built from (``df.attrs["crsp_vintage"]``, e.g. ``"202609"``),
so that a result can be tied to the copy it was computed on. Copies kept in
the local cache are timestamped; a refresh replaces them.

Example::

    from pwb_toolbox.datasets import load_french

    ff5 = load_french("ff5")                                 # monthly, decimal
    mom = load_french("mom", frequency="daily")
    ind48 = load_french("ind48", weighting="equal")          # equal-weighted
    blocks = load_french_blocks("25_Portfolios_5x5")         # every block of the file
    blocks["number_of_firms_in_portfolios"]

Returns are converted to decimals (the files publish percents); the other
blocks (number of firms, average size, BE/ME...) are left as published.
``-99.99`` and ``-999`` are the library's missing values and become NaN.
Monthly rows are dated at the month end, annual rows at December 31.

Cache: ``cache_dir`` if given, else ``$PWB_FRENCH_CACHE_DIR``, else
``$PWB_CACHE_DIR/french``, else ``~/.cache/pwb/french``. A cached copy younger
than ``max_age_days`` (default 7) is used without any network access;
``refresh=True`` downloads again. If the site cannot be reached, a stale copy
is used with a warning rather than failing.
"""
from __future__ import annotations

import difflib
import io
import os
import re
import time
import warnings
import zipfile
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
LIBRARY_PAGE = "data_library.html"
SOURCE = "Kenneth R. French Data Library"
LICENCE_NOTE = (
    "Data from Kenneth R. French's Data Library, downloaded on the user's "
    "machine; not redistributed by Papers With Backtest."
)

#: Short names for the files most papers use. Any file name of the library
#: (without ``_CSV.zip`` and without the ``_daily``/``_weekly`` suffix) also works.
FRENCH_ALIASES = {
    "ff3": "F-F_Research_Data_Factors",
    "ff5": "F-F_Research_Data_5_Factors_2x3",
    "mom": "F-F_Momentum_Factor",
    "momentum": "F-F_Momentum_Factor",
    "st_rev": "F-F_ST_Reversal_Factor",
    "lt_rev": "F-F_LT_Reversal_Factor",
    "25_size_bm": "25_Portfolios_5x5",
    "100_size_bm": "100_Portfolios_10x10",
    **{f"ind{n}": f"{n}_Industry_Portfolios" for n in (5, 10, 12, 17, 30, 38, 48, 49)},
}

FREQUENCIES = ("monthly", "annual", "daily", "weekly")
WEIGHTINGS = ("value", "equal")
MISSING_VALUES = (-99.99, -999.0)
DEFAULT_MAX_AGE_DAYS = 7.0

_ZIP_HREF = re.compile(r'href\s*=\s*"ftp/([^"]+?_CSV\.zip)"', re.IGNORECASE)
_DATA_ROW = re.compile(r"^\s*(\d{4}|\d{6}|\d{8})\s*,")
_CRSP_VINTAGE = re.compile(r"(\d{6})\s+CRSP", re.IGNORECASE)
_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_HTTP_ATTEMPTS = 3
_HTTP_TIMEOUT = 60
_USER_AGENT = "pwb-toolbox (Kenneth French Data Library loader)"


class FrenchDataError(LookupError):
    """A name, frequency or block the library does not have."""


# --------------------------------------------------------------------------- #
# Cache                                                                       #
# --------------------------------------------------------------------------- #
def french_cache_dir(cache_dir: Optional[str] = None) -> str:
    """The directory holding the downloaded copies (see the module docstring)."""
    if cache_dir:
        return os.path.expanduser(cache_dir)
    explicit = os.getenv("PWB_FRENCH_CACHE_DIR")
    if explicit:
        return os.path.expanduser(explicit)
    shared = os.getenv("PWB_CACHE_DIR")
    if shared:
        return os.path.join(os.path.expanduser(shared), "french")
    return os.path.join(os.path.expanduser("~"), ".cache", "pwb", "french")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_STAMP_FORMAT)


def _cached_copies(root: str, filename: str) -> list[tuple[datetime, str]]:
    """``[(downloaded_at, path)]`` of ``filename`` in the cache, newest first."""
    if not os.path.isdir(root):
        return []
    prefix = filename + "."
    found = []
    for entry in os.listdir(root):
        # Compared without case: the site serves both "_daily" and "_Daily",
        # and a cache on a case-insensitive disk must not hold both.
        if not entry.lower().startswith(prefix.lower()) or entry.endswith(".part"):
            continue
        stamp = entry[len(prefix):]
        try:
            when = datetime.strptime(stamp, _STAMP_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        found.append((when, os.path.join(root, entry)))
    return sorted(found, reverse=True)


def _store(root: str, filename: str, payload: bytes, moment: datetime) -> str:
    """Write ``payload`` atomically as the newest copy and drop the older ones."""
    os.makedirs(root, exist_ok=True)
    older = _cached_copies(root, filename)
    final = os.path.join(root, f"{filename}.{_stamp(moment)}")
    partial = final + ".part"
    with open(partial, "wb") as fh:
        fh.write(payload)
    os.replace(partial, final)
    for _, path in older:
        if path != final:
            try:
                os.remove(path)
            except OSError:
                pass
    return final


def _is_fresh(moment: datetime, max_age_days: Optional[float]) -> bool:
    if max_age_days is None:
        return True
    age = datetime.now(timezone.utc) - moment
    return age.total_seconds() <= max_age_days * 86400.0


# --------------------------------------------------------------------------- #
# Network                                                                     #
# --------------------------------------------------------------------------- #
def _http_get(url: str) -> bytes:
    """The body of ``url``; retried, then ``requests.RequestException``."""
    last = None
    for attempt in range(_HTTP_ATTEMPTS):
        try:
            resp = requests.get(url, timeout=_HTTP_TIMEOUT, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last = exc
            if attempt + 1 < _HTTP_ATTEMPTS:
                time.sleep(1.5 * (attempt + 1))
    raise last


def _fetch(filename: str, url: str, root: str, refresh: bool, max_age_days, validate):
    """``(payload, downloaded_at)`` from the cache or the site.

    A fresh cached copy is served without any request. Otherwise the file is
    downloaded, validated and stored; if that fails and a stale copy exists,
    the stale copy is served with a warning.
    """
    copies = _cached_copies(root, filename)
    if copies and not refresh and _is_fresh(copies[0][0], max_age_days):
        with open(copies[0][1], "rb") as fh:
            return fh.read(), copies[0][0]
    try:
        payload = _http_get(url)
        validate(payload)
    except (requests.RequestException, ValueError) as exc:
        if copies:
            warnings.warn(
                f"{SOURCE}: could not download {url} ({type(exc).__name__}: {exc}); "
                f"using the copy downloaded on {copies[0][0]:%Y-%m-%d %H:%M} UTC.",
                RuntimeWarning,
                stacklevel=3,
            )
            with open(copies[0][1], "rb") as fh:
                return fh.read(), copies[0][0]
        raise
    moment = datetime.now(timezone.utc).replace(microsecond=0)
    _store(root, filename, payload, moment)
    return payload, moment


def _validate_page(payload: bytes) -> None:
    if not _ZIP_HREF.search(payload.decode("latin-1")):
        raise ValueError("the Data Library page lists no *_CSV.zip file")


def _validate_zip(payload: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            if not any(n.lower().endswith(".csv") for n in zf.namelist()):
                raise ValueError("the zip holds no CSV file")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"not a zip file: {exc}") from exc


# --------------------------------------------------------------------------- #
# The list of files                                                           #
# --------------------------------------------------------------------------- #
def _parse_listing(html: str) -> list[str]:
    """The ``*_CSV.zip`` file names linked from the Data Library page, in order."""
    seen, names = set(), []
    for name in _ZIP_HREF.findall(html):
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _listing(root: str, refresh: bool, max_age_days) -> list[str]:
    payload, _ = _fetch(
        LIBRARY_PAGE, BASE_URL + LIBRARY_PAGE, root, refresh, max_age_days, _validate_page
    )
    return _parse_listing(payload.decode("latin-1"))


def french_datasets(refresh: bool = False, max_age_days=DEFAULT_MAX_AGE_DAYS,
                    cache_dir: Optional[str] = None) -> list[str]:
    """Every file of the Data Library, as the names ``load_french`` accepts.

    Read from the library's page (cached like the files). ``_daily`` and
    ``_weekly`` variants are listed as they are published.
    """
    root = french_cache_dir(cache_dir)
    return [n[: -len("_CSV.zip")] for n in _listing(root, refresh, max_age_days)]


def _base_name(name: str) -> str:
    key = name.strip()
    if key.lower().endswith("_csv.zip"):
        key = key[: -len("_CSV.zip")]
    return FRENCH_ALIASES.get(key.lower(), key)


def _wanted_stem(base: str, frequency: str) -> str:
    lowered = base.lower()
    if lowered.endswith("_daily") or lowered.endswith("_weekly"):
        return base
    if frequency in ("daily", "weekly"):
        return f"{base}_{frequency}"
    return base


def _resolve(stem: str, files: list[str]) -> str:
    """The file of the listing whose stem is ``stem``, compared without case."""
    by_lower = {f[: -len("_CSV.zip")].lower(): f for f in files}
    hit = by_lower.get(stem.lower())
    if hit:
        return hit
    close = difflib.get_close_matches(stem.lower(), list(by_lower), n=5, cutoff=0.6)
    hint = ", ".join(by_lower[c][: -len("_CSV.zip")] for c in close)
    raise FrenchDataError(
        f"{SOURCE} has no file {stem!r}"
        + (f"; close names: {hint}" if hint else "")
        + ". french_datasets() lists them all; aliases: " + ", ".join(sorted(FRENCH_ALIASES))
    )


# --------------------------------------------------------------------------- #
# Parsing                                                                     #
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _characteristic_key(title_lines: list[str]) -> str:
    """A short key for a characteristic table: its naming line, up to "Calculated".

    The BE/ME, OP and investment tables carry four-line titles (the formula,
    the window, the adjustment); the full title stays in ``attrs["title"]``.
    """
    lines = [t for t in title_lines if t and not t.lower().startswith("for portfolios formed")]
    head = lines[0] if lines else ""
    head = re.split(r"\s+calculated\b", head, flags=re.IGNORECASE)[0]
    return _slug(head) or "table"


def _dates(tokens: list[str]) -> pd.DatetimeIndex:
    width = len(tokens[0])
    if any(len(t) != width for t in tokens):
        raise ValueError("a block mixes date formats")
    if width == 8:
        return pd.DatetimeIndex(pd.to_datetime(tokens, format="%Y%m%d"))
    if width == 6:
        return pd.DatetimeIndex(pd.to_datetime(tokens, format="%Y%m") + pd.offsets.MonthEnd(0))
    return pd.DatetimeIndex(pd.to_datetime([t + "1231" for t in tokens], format="%Y%m%d"))


def _block_frequency(width: int, file_frequency: str) -> str:
    if width == 4:
        return "annual"
    if width == 6:
        return "monthly"
    return "weekly" if file_frequency == "weekly" else "daily"


def _kind_and_weighting(title: str):
    lowered = title.lower()
    weighting = None
    # "Value Weighted", "Value-Weighted" and "Value Weight Returns" all occur.
    if re.search(r"value[\s-]*weight", lowered):
        weighting = "value"
    elif re.search(r"equal[\s-]*weight", lowered):
        weighting = "equal"
    # "Value-Weighted Average of Prior Returns" is a characteristic, not a return.
    if not title or "factors" in lowered or ("returns" in lowered and "average of" not in lowered):
        return "returns", weighting
    return "characteristic", weighting


def _raw_blocks(text: str):
    """``[(title_lines, header, rows)]``: every table of a library CSV.

    A table is a header line starting with a comma, followed (sometimes after
    a blank line) by rows starting with a 4-, 6- or 8-digit date. Its title is the run of non-blank lines just
    above the header (empty for the untitled first block of the factor files).
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks, run, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            run = []
            i += 1
            continue
        # The first row may sit after a blank line (the annual table of
        # Portfolios_Formed_on_VAR does that).
        first = i + 1
        while first < len(lines) and not lines[first].strip():
            first += 1
        if line.lstrip().startswith(",") and first < len(lines) and _DATA_ROW.match(lines[first]):
            header = [h.strip() for h in line.lstrip()[1:].split(",")]
            while header and not header[-1]:
                header.pop()
            rows = []
            i = first
            while i < len(lines) and _DATA_ROW.match(lines[i]):
                rows.append(lines[i])
                i += 1
            blocks.append(([t.strip() for t in run], header, rows))
            run = []
            continue
        run.append(line)
        i += 1
    return blocks


def _frame(header: list[str], rows: list[str], scale: float) -> pd.DataFrame:
    tokens, values = [], []
    width = len(header)
    for row in rows:
        parts = [p.strip() for p in row.split(",")]
        cells = parts[1: 1 + width]
        cells += [""] * (width - len(cells))
        tokens.append(parts[0])
        values.append([float(c) if c else np.nan for c in cells])
    data = np.asarray(values, dtype=float).reshape(len(rows), width)
    missing = np.zeros_like(data, dtype=bool)
    for marker in MISSING_VALUES:
        missing |= np.isclose(data, marker, rtol=0.0, atol=1e-9)
    data[missing] = np.nan
    frame = pd.DataFrame(data / scale, index=_dates(tokens), columns=header)
    frame.index.name = "date"
    return frame


def parse_french_csv(text: str, file_frequency: str = "monthly") -> dict:
    """Every table of one library CSV, as ``{key: DataFrame}`` in file order.

    Keys: ``"monthly"``, ``"annual"``, ``"daily"``, ``"weekly"`` for the
    untitled factor tables and the "Annual Factors" table; ``"value_monthly"``,
    ``"equal_annual"``, ``"value_daily"``... for the weighted return tables;
    a slug of the naming line of the title for anything else (``"number_of_firms_in_portfolios"``,
    ``"average_firm_size"``, ...). Each frame's ``attrs`` carry ``title``,
    ``kind`` (``"returns"`` or ``"characteristic"``), ``frequency`` and
    ``weighting``. Returns are divided by 100; the other tables are not.
    """
    out = {}
    vintage = _CRSP_VINTAGE.search(text[:2000])
    for title_lines, header, rows in _raw_blocks(text):
        title = " ".join(t for t in title_lines if t)
        kind, weighting = _kind_and_weighting(title)
        width = len(rows[0].split(",", 1)[0].strip())
        frequency = _block_frequency(width, file_frequency)
        if kind == "returns":
            key = frequency if weighting is None else f"{weighting}_{frequency}"
        else:
            key = _characteristic_key(title_lines)
        base, n = key, 2
        while key in out:
            key = f"{base}_{n}"
            n += 1
        frame = _frame(header, rows, 100.0 if kind == "returns" else 1.0)
        frame.attrs.update({
            "title": title,
            "kind": kind,
            "frequency": frequency,
            "weighting": weighting,
            "units": "decimal return" if kind == "returns" else "as published",
            "crsp_vintage": vintage.group(1) if vintage else None,
        })
        out[key] = frame
    if not out:
        raise ValueError("no table found in the CSV")
    return out


# --------------------------------------------------------------------------- #
# Public loaders                                                              #
# --------------------------------------------------------------------------- #
def _check_frequency(frequency: str) -> str:
    frequency = str(frequency).lower()
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {FREQUENCIES}, not {frequency!r}")
    return frequency


def _cached_by_stem(root: str, stem: str, max_age_days, refresh: bool):
    """A fresh cached zip for ``stem`` (any case): its file name, or ``None``."""
    if refresh or not os.path.isdir(root):
        return None
    target = f"{stem}_CSV.zip".lower()
    for entry in os.listdir(root):
        filename = entry.rsplit(".", 1)[0] if "." in entry else entry
        if filename.lower() == target:
            copies = _cached_copies(root, filename)
            if copies and _is_fresh(copies[0][0], max_age_days):
                return filename
    return None


def load_french_blocks(name: str, frequency: str = "monthly", refresh: bool = False,
                       max_age_days=DEFAULT_MAX_AGE_DAYS,
                       cache_dir: Optional[str] = None) -> dict:
    """Every table of one Data Library file, as ``{key: DataFrame}``.

    ``name`` is an alias of ``FRENCH_ALIASES`` (``"ff5"``, ``"mom"``,
    ``"ind48"``...) or a file name of the library (``french_datasets()``).
    ``frequency`` picks the file: ``"monthly"`` and ``"annual"`` read the main
    file (which holds both), ``"daily"`` and ``"weekly"`` their own files. See
    ``parse_french_csv`` for the keys. Each frame's ``attrs`` also carry
    ``source``, ``file``, ``url``, ``downloaded_at`` (ISO, UTC) and
    ``licence``. There is no historical vintage: see the module docstring.
    """
    frequency = _check_frequency(frequency)
    root = french_cache_dir(cache_dir)
    stem = _wanted_stem(_base_name(name), frequency)
    if stem.lower().endswith("_breakpoints"):
        # Percentile tables with a count column and no full header row: another
        # layout, and not returns. Not supported rather than misread.
        raise FrenchDataError(f"{stem}: the breakpoint files are not supported by this loader")
    filename = _cached_by_stem(root, stem, max_age_days, refresh)
    if filename is None:
        try:
            files = _listing(root, refresh, max_age_days)
        except requests.RequestException:
            # Offline and no listing: a stale copy of the file itself still serves.
            stale = _cached_by_stem(root, stem, None, False)
            if stale is None:
                raise
            filename = stale
        else:
            filename = _resolve(stem, files)
    url = BASE_URL + "ftp/" + filename
    payload, downloaded_at = _fetch(filename, url, root, refresh, max_age_days, _validate_zip)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        text = zf.read(csvs[0]).decode("latin-1")
    file_frequency = "weekly" if stem.lower().endswith("_weekly") else (
        "daily" if stem.lower().endswith("_daily") else "monthly")
    blocks = parse_french_csv(text, file_frequency)
    for frame in blocks.values():
        frame.attrs.update({
            "source": SOURCE,
            "file": filename,
            "url": url,
            "downloaded_at": downloaded_at.isoformat(),
            "licence": LICENCE_NOTE,
        })
    return blocks


def load_french(name: str, frequency: str = "monthly", weighting: str = "value",
                block: Optional[str] = None, refresh: bool = False,
                max_age_days=DEFAULT_MAX_AGE_DAYS,
                cache_dir: Optional[str] = None) -> pd.DataFrame:
    """Returns of one Data Library file, as a DataFrame of decimal returns.

    Parameters
    ----------
    name : str
        An alias (``"ff3"``, ``"ff5"``, ``"mom"``, ``"st_rev"``, ``"lt_rev"``,
        ``"ind10"`` ... ``"ind49"``, ``"25_size_bm"``, ``"100_size_bm"``) or any
        file name of the library (``french_datasets()``), e.g.
        ``"Portfolios_Formed_on_ME"``.
    frequency : {"monthly", "annual", "daily", "weekly"}
    weighting : {"value", "equal"}
        For portfolio files, which return table; ignored by factor files.
    block : str, optional
        A table key of ``load_french_blocks`` to return instead (e.g.
        ``"number_of_firms_in_portfolios"``).
    refresh : bool
        Download again even if the cached copy is fresh.
    max_age_days : float or None
        Age beyond which a cached copy is downloaded again (default 7);
        ``None`` never re-downloads a cached copy.
    cache_dir : str, optional
        Where the copies live (see the module docstring for the default).

    Index: the date (month end, December 31, or the trading day). Columns: as
    published (``"Mkt-RF"``, ``"SMB"``, ``"Agric"``, ``"SMALL LoBM"``...).
    Missing values (``-99.99``/``-999``) are NaN. ``attrs["downloaded_at"]``
    and ``attrs["crsp_vintage"]`` say which copy this is: the library rewrites
    its whole history at each update and serves no older vintage, so a result
    is reproducible only from the same local copy.

    Licence: Kenneth R. French's data, downloaded on the user's machine; not
    redistributed by Papers With Backtest.
    """
    frequency = _check_frequency(frequency)
    blocks = load_french_blocks(name, frequency, refresh=refresh,
                                max_age_days=max_age_days, cache_dir=cache_dir)
    if block is not None:
        if block not in blocks:
            raise FrenchDataError(f"no table {block!r}; tables: {', '.join(blocks)}")
        return blocks[block]
    if weighting not in WEIGHTINGS:
        raise ValueError(f"weighting must be one of {WEIGHTINGS}, not {weighting!r}")
    candidates = {
        k: f for k, f in blocks.items()
        if f.attrs["kind"] == "returns" and f.attrs["frequency"] == frequency
    }
    weighted = {k: f for k, f in candidates.items() if f.attrs["weighting"] == weighting}
    if weighted:
        candidates = weighted
    elif any(f.attrs["weighting"] for f in candidates.values()):
        candidates = {}
    if len(candidates) != 1:
        raise FrenchDataError(
            f"{name!r}: {len(candidates)} {frequency} {weighting}-weighted return tables; "
            f"pass block= one of: {', '.join(blocks)}"
        )
    return next(iter(candidates.values()))
