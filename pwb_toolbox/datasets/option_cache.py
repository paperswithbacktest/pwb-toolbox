"""Disk cache of the bytes ``load_option_chain`` reads from ``Options-Daily-Price``.

Why bytes, and not decoded chains
---------------------------------
A backtest that trades options reads its chains month by month from inside
``next()``: every month, every chunk of underlyings, one footer and a few
dozen row groups fetched by HTTP range requests. The profile of the slowest
strategies (A3, 23 Nov 2026) put 75-85 % of their time inside
``ParquetFile.read_row_groups``. Measured on the data host the same day, one
month (2020-03, 6 row groups, 9 columns): 2.35 s to fetch and decode, 0.021 s
to decode the same bytes from memory. pyarrow reads the ranges from its I/O
threads, so a profile of the main thread shows the wait as time spent in
``read_row_groups``: the cost is the network round trips, not the decoding.

So the cache keeps the **bytes of the files**, not what is made of them:

* it is exact by construction: a file of a dataset revision never changes, the
  bytes served from disk are the bytes the Hub would have sent, and pyarrow,
  the filters and the conversion to pandas run on them exactly as before;
* it is shared by every caller, whatever the underlyings, the window or the
  columns: two strategies that read different columns of the same row groups
  share the blocks they both touch.

What makes an entry valid
-------------------------
The key of a block names everything its content depends on: the dataset
(``paperswithbacktest/Options-Daily-Price``), the **exact revision** (the
commit hash the loader resolved through ``_hub_snapshot`` and put in the URL),
the file, the block's index and the block size, and the format of this
module. Nothing of the caller's request (underlyings, dates, columns) shapes a
block, and no code but this module's writes one, so neither is in the key.
There is no TTL: a new commit on the Hub is a new revision, hence new keys; the
old blocks are never asked for again and the size cap removes them.

When it is off
--------------
Nothing is read from or written to the cache when:

* ``PWB_CACHE=0`` (every cache of the package), or ``PWB_OPTIONS_CACHE=0``
  (this one only);
* the process is degraded (``prepared_cache.note_degraded``: a cost table that
  could not be read, ...), offline (``PWB_HF_OFFLINE`` / ``HF_HUB_OFFLINE``),
  or the Hub was unreachable and the revision came from a local snapshot;
* the revision is unknown: files listed by the subscriber API carry none, so
  they are read over the network as before.

A degraded or offline run therefore behaves exactly as without the cache.

Storage
-------
``$PWB_CACHE_DIR/options/v1`` (``~/.cache/pwb_toolbox/options/v1`` by
default), capped at ``PWB_OPTIONS_CACHE_MAX_GB`` (20), least recently used
first. Per file: one ``.meta`` entry (size and the last 64 KiB, which hold the
Parquet footer) and one entry per 256 KiB block. Each entry is a small header
(magic, length, CRC32) and the bytes; it is written to a temporary name and
renamed into place, so concurrent writers of the same block each leave a whole
file and a reader never sees a partial one. An entry that fails its checks
(a crash can leave a renamed but unwritten file: there is no fsync) is
deleted and fetched again.
"""

from __future__ import annotations

import hashlib
import os
import struct
import tempfile
import threading
import zlib

FORMAT = 1
BLOCK_SIZE = 256 * 1024
_MAGIC = b"PWBOBK01"
_HEAD = struct.Struct("<8sQQI")  # magic, block size (or file size for .meta), payload length, crc32
_MAX_GB_DEFAULT = 20.0
#: Bytes written by this process since the size cap was last enforced; the cap
#: is enforced on the first write and then every twentieth of the cap.
_written_since_scan = [None]
_LOCK = threading.Lock()

stats = {"meta_hits": 0, "meta_misses": 0, "block_hits": 0, "block_misses": 0,
         "bytes_from_cache": 0, "bytes_fetched": 0, "stored": 0, "errors": 0, "bypassed": 0}

#: ``{url: (repo, sha, file name)}`` of the Hub files ``_hf_sources`` listed,
#: so ``_open`` knows the revision of a URL without parsing it.
_IDENTITIES: dict = {}


def reset_stats() -> None:
    for key in stats:
        stats[key] = 0


def register(url: str, repo: str, sha, filename: str) -> None:
    if sha:
        _IDENTITIES[url] = (repo, str(sha), filename)


def identity(url: str):
    return _IDENTITIES.get(url)


def _offline() -> bool:
    return (os.getenv("PWB_HF_OFFLINE", "0") != "0"
            or os.getenv("HF_HUB_OFFLINE", "0") not in ("", "0"))


def active(repo: str) -> bool:
    """Whether the cache may be read and written now, for ``repo``."""
    from . import prepared_cache
    from . import _HUB_LOCAL_FALLBACK

    if not prepared_cache.enabled() or os.getenv("PWB_OPTIONS_CACHE", "1").strip() == "0":
        return False
    if prepared_cache._DEGRADED or _offline() or repo in _HUB_LOCAL_FALLBACK:
        return False
    return True


def cache_root() -> str:
    root = os.getenv("PWB_CACHE_DIR")
    if not root:
        base = os.getenv("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        root = os.path.join(base, "pwb_toolbox")
    return os.path.join(root, "options", f"v{FORMAT}")


def _file_dir(root: str, repo: str, sha: str, filename: str) -> str:
    # The file name is hashed: it may hold slashes (``data/train-2024-01.parquet``).
    tag = hashlib.sha256(filename.encode()).hexdigest()[:24]
    return os.path.join(root, repo.replace("/", "--"), sha, f"b{BLOCK_SIZE}", tag)


# --------------------------------------------------------------------------- #
# Entries                                                                     #
# --------------------------------------------------------------------------- #
def _write_entry(path: str, size_field: int, payload: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_HEAD.pack(_MAGIC, size_field, len(payload), zlib.crc32(payload)))
            fh.write(payload)
        # No fsync: a block is cheap to fetch again, and one fsync per 256 KiB
        # tripled the time of a first read on the data host. After a crash, a
        # renamed but unwritten entry fails its CRC and is fetched again.
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _account(len(payload) + _HEAD.size)


def _read_entry(path: str, size_field: int = None):
    """``(size_field, payload)``, ``None`` if absent; a malformed entry is deleted and ``None``."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        return None
    except OSError:
        stats["errors"] += 1
        return None
    ok = len(data) >= _HEAD.size
    if ok:
        magic, field, length, crc = _HEAD.unpack_from(data)
        payload = data[_HEAD.size:]
        ok = (magic == _MAGIC and length == len(payload) and zlib.crc32(payload) == crc
              and (size_field is None or field == size_field))
    if not ok:
        stats["errors"] += 1
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    try:
        os.utime(path, None)
    except OSError:
        pass
    return field, payload


def _cap_bytes() -> float:
    try:
        return float(os.getenv("PWB_OPTIONS_CACHE_MAX_GB", _MAX_GB_DEFAULT)) * 1024**3
    except ValueError:
        return _MAX_GB_DEFAULT * 1024**3


def _account(nbytes: int) -> None:
    with _LOCK:
        due = _written_since_scan[0] is None or _written_since_scan[0] + nbytes > _cap_bytes() / 20
        _written_since_scan[0] = 0 if due else _written_since_scan[0] + nbytes
    if due:
        evict(cache_root())


def evict(root: str) -> None:
    """Remove the least recently used entries until the cache fits under the cap."""
    cap = _cap_bytes()
    entries = []
    for directory, _, names in os.walk(root):
        for name in names:
            if name.startswith(".tmp-"):
                continue
            path = os.path.join(directory, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            entries.append((st.st_mtime, st.st_size, path))
    total = sum(size for _, size, _ in entries)
    for _, size, path in sorted(entries):
        if total <= cap:
            break
        try:
            os.unlink(path)
            total -= size
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# The file object                                                             #
# --------------------------------------------------------------------------- #
def make_cached_file(base_cls):
    """A subclass of ``RangeFile`` that keeps what it fetches (defined here,
    built in ``options`` so the base class is the one the loader uses)."""

    class CachedRangeFile(base_cls):
        def __init__(self, url, headers, ident, session=None):
            super().__init__(url, headers, session)
            self.repo, self.sha, self.filename = ident
            self.dir = _file_dir(cache_root(), self.repo, self.sha, self.filename)

        # -- footer ---------------------------------------------------------
        def _fetch_tail(self):
            meta = os.path.join(self.dir, "meta")
            if active(self.repo):
                entry = _read_entry(meta)
                if entry is not None:
                    size, payload = entry
                    if len(payload) <= size:
                        stats["meta_hits"] += 1
                        self._size, self._tail_start, self._tail = size, size - len(payload), payload
                        stats["bytes_from_cache"] += len(payload)
                        return
            stats["meta_misses"] += 1
            super()._fetch_tail()
            # The tail must end the file, or it is not what a later reader expects.
            if active(self.repo) and self._tail_start + len(self._tail) == self._size:
                try:
                    _write_entry(meta, self._size, self._tail)
                    stats["stored"] += 1
                except OSError:
                    stats["errors"] += 1

        # -- body -----------------------------------------------------------
        def read(self, n=-1):
            if n is None or n < 0:
                n = self.size - self.pos
            if n == 0 or self.pos >= self.size:
                return b""
            end = min(self.pos + n, self.size)
            if self._tail_start is not None and self._tail_start <= self.pos and end <= self._tail_start + len(self._tail):
                return super().read(n)
            if not active(self.repo):
                stats["bypassed"] += 1
                return super().read(n)
            data = self._blocks(self.pos, end)
            if data is None:
                return super().read(n)
            self.pos += len(data)
            return data

        def _block_len(self, i):
            return min(BLOCK_SIZE, self._size - i * BLOCK_SIZE)

        def _blocks(self, start, end):
            first, last = start // BLOCK_SIZE, (end - 1) // BLOCK_SIZE
            got = {}
            for i in range(first, last + 1):
                entry = _read_entry(os.path.join(self.dir, f"{i}.blk"), BLOCK_SIZE)
                if entry is not None and len(entry[1]) == self._block_len(i):
                    got[i] = entry[1]
                    stats["block_hits"] += 1
                    stats["bytes_from_cache"] += len(entry[1])
            missing = [i for i in range(first, last + 1) if i not in got]
            # Contiguous missing blocks come in one request, as the read they serve would.
            runs = []
            for i in missing:
                if runs and runs[-1][1] == i - 1:
                    runs[-1][1] = i
                else:
                    runs.append([i, i])
            fetched = {}
            for a, b in runs:
                lo, hi = a * BLOCK_SIZE, min((b + 1) * BLOCK_SIZE, self._size)
                data = self._get(f"bytes={lo}-{hi - 1}").content
                self.bytes_read += len(data)
                stats["bytes_fetched"] += len(data)
                if len(data) != hi - lo:
                    # A short answer: nothing is stored, and the read is redone
                    # exactly as the plain reader does it.
                    stats["errors"] += 1
                    return None
                for i in range(a, b + 1):
                    fetched[i] = data[(i - a) * BLOCK_SIZE:(i - a) * BLOCK_SIZE + self._block_len(i)]
            for i, part in fetched.items():
                got[i] = part
                stats["block_misses"] += 1
                if active(self.repo):
                    try:
                        _write_entry(os.path.join(self.dir, f"{i}.blk"), BLOCK_SIZE, part)
                        stats["stored"] += 1
                    except OSError:
                        stats["errors"] += 1
            joined = b"".join(got[i] for i in range(first, last + 1))
            offset = start - first * BLOCK_SIZE
            return joined[offset:offset + (end - start)]

    return CachedRangeFile
