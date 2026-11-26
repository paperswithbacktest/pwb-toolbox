"""Disk cache of prepared data: what ``get_pricing``, ``load_dataset`` and
``get_cost_schedules`` return, kept between processes.

Why
---
Every backtest of a campaign is its own process, and each one rebuilds the
same things from the same shards: the price panel of a point-in-time universe
(779 monthly shards filtered, cut by membership, pivoted), the fundamentals
tables, the cost schedules. The in-process memo (``_READ_MEMO``) dies with the
process; this cache does not.

What makes an entry valid
-------------------------
An entry is never "fresh" or "stale" by age: there is no TTL. It is valid
because its key names everything its content was computed from:

* the call -- function, every argument (defaults included), the ``PWB_*``
  settings of the environment and whether the subscriber API is in use;
* the code -- a hash of every ``.py`` file of the installed ``pwb_toolbox``,
  and the versions of Python, pandas, numpy and pyarrow;
* the data -- the **exact revision** (commit hash) of every dataset the process
  had resolved when the result was computed.

The last item is deliberately broad. Recording only the datasets a call reads
while it runs would miss the ones it reads through a per-process cache filled
earlier (the point-in-time universe, the cost tables), so the whole set the
process had resolved is recorded instead. More datasets in a key can only make
it miss more often, never serve something computed from another revision.

At lookup, the revisions are resolved again the way the loaders resolve them
(``_hub_snapshot`` for the Hub, the API's index, the cost-table loaders for the
cost tables) and the entry is read only if every one is the same. A new commit
on the Hub is a new key: the old entry is simply never asked for again, and the
size cap (least recently used first) eventually removes it.

What is never cached
--------------------
A result is not stored, and the cache is not read, when any of these holds --
in each case the alternative would be an entry whose key does not describe its
content:

* a dataset's revision is unknown (the subscriber API without the Hub index);
* the process is in a degraded mode: a cost table that could not be read (the
  Roll or floor fallback, e.g. ``HF_HUB_OFFLINE=1``, which makes
  ``list_repo_files`` fail), a Roll fallback whose prices did not load, the
  catalogue index unreachable. A degraded run stays degraded with the cache on,
  and its result is never served to a healthy one;
* no dataset revision was resolved at all (a loader replaced in a test);
* ``PWB_PIT_UNIVERSE_DIR`` points at local files, which carry no revision;
* a call made from inside another cached call (only the outermost is cached),
  inside ``superset_reads()``, or from ``get_pricing`` with a shard window;
* the minute datasets and the option chains (bounded reads, and large);
* an argument the key cannot describe exactly.

Side effects are replayed: what the computation printed to stdout (the
``[costs]`` and ``Warning:`` lines the harness reads) and the ``pwb_toolbox``
warnings it raised are written and raised again on a hit.

Storage
-------
``$PWB_CACHE_DIR/prepared`` (``~/.cache/pwb_toolbox/prepared`` by default),
capped at ``PWB_PREPARED_CACHE_MAX_GB`` (10), least recently used first;
``PWB_CACHE=0`` turns it off. One file per entry: a JSON header, a pickle
(protocol 5) whose numpy buffers are stored out of band, aligned, and mapped
copy-on-write on read -- a 400 MB panel is mapped, not read, and a caller that
writes into it gets private pages. Files are written to a temporary name and
renamed into place, so two processes writing the same key both leave a whole
file, and a reader never sees a partial one. A file that fails to read is
deleted and recomputed.

The pickle is read back only from this directory, which the user's own
processes write; it is not a format to exchange.
"""

from __future__ import annotations

import functools
import glob
import hashlib
import inspect
import io
import json
import mmap
import os
import pickle
import struct
import sys
import tempfile
import threading
import time
import warnings
from contextvars import ContextVar
from datetime import date, datetime

FORMAT = 1
_MAGIC = b"PWBPREP1"
_END = b"PWBEND01"
_ALIGN = 64
_MAX_GB_DEFAULT = 10.0
_MAX_VARIANTS = 8

# --------------------------------------------------------------------------- #
# Revisions resolved by this process                                          #
# --------------------------------------------------------------------------- #
#: ``{(kind, name): sha or None}``. ``kind`` is ``"hub"`` (``_hub_snapshot``),
#: ``"api"`` (the subscriber API, pinned through the Hub index) or ``"table"``
#: (a cost table read by ``backtesting.commission``). ``None`` = read, but at a
#: revision nobody can name.
_RESOLVED: dict = {}
#: Why the process is degraded, if it is: nothing is read or stored then.
_DEGRADED: list = []
#: ``{repo: loader}`` for the ``"table"`` revisions: the loader reads the
#: table (once per process) and notes its revision, or its failure.
_TABLE_LOADERS: dict = {}
_LOCK = threading.Lock()

_DEPTH: ContextVar = ContextVar("pwb_prepared_cache_depth", default=0)

#: Counters for this process (read by the tests and the proof runs).
stats = {"hits": 0, "misses": 0, "stored": 0, "bypassed": 0, "errors": 0,
         "seconds_saved_estimate": 0.0}


def note_revision(kind: str, name: str, sha) -> None:
    """Record that this process read ``name`` at revision ``sha`` (``None``: unknown)."""
    with _LOCK:
        _RESOLVED[(kind, name)] = None if sha is None else str(sha)


def note_degraded(reason: str) -> None:
    """Record that this process fell back to a degraded mode; the cache is off from then on."""
    with _LOCK:
        if reason not in _DEGRADED:
            _DEGRADED.append(reason)


def revision_of(kind: str, name: str):
    """The revision this process noted for ``name``, or ``None``."""
    with _LOCK:
        return _RESOLVED.get((kind, name))


def register_table(repo: str, loader) -> None:
    _TABLE_LOADERS[repo] = loader


def reset_process_state() -> None:
    """Forget the revisions and the degraded flag (tests)."""
    with _LOCK:
        _RESOLVED.clear()
        _DEGRADED.clear()
    for key in stats:
        stats[key] = 0.0 if isinstance(stats[key], float) else 0


def enabled() -> bool:
    return os.getenv("PWB_CACHE", "1").strip() != "0"


def cache_root() -> str:
    root = os.getenv("PWB_CACHE_DIR")
    if not root:
        base = os.getenv("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
        root = os.path.join(base, "pwb_toolbox")
    return os.path.join(root, "prepared", f"v{FORMAT}")


# --------------------------------------------------------------------------- #
# Keys                                                                        #
# --------------------------------------------------------------------------- #
class _Uncacheable(Exception):
    pass


def _canon(obj):
    """A JSON-able, type-tagged rendering of an argument, or ``_Uncacheable``."""
    import numpy as np
    import pandas as pd

    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return ["i", int(obj)]
    if isinstance(obj, (float, np.floating)):
        return ["f", float(obj).hex()]
    if isinstance(obj, str):
        return ["s", obj]
    if isinstance(obj, pd.Timestamp):
        return ["ts", obj.isoformat(), str(obj.tz)]
    if isinstance(obj, datetime):
        return ["dt", obj.isoformat()]
    if isinstance(obj, date):
        return ["d", obj.isoformat()]
    if isinstance(obj, (list, tuple)):
        return ["l" if isinstance(obj, list) else "t", [_canon(x) for x in obj]]
    if isinstance(obj, (set, frozenset)):
        items = [_canon(x) for x in obj]
        return ["set", sorted(items, key=lambda x: json.dumps(x, sort_keys=True))]
    if isinstance(obj, dict):
        items = [[_canon(k), _canon(v)] for k, v in obj.items()]
        return ["map", sorted(items, key=lambda kv: json.dumps(kv[0], sort_keys=True))]
    raise _Uncacheable(type(obj).__name__)


_CODE_VERSION = None


def code_version() -> str:
    """Hash of the package's source and of the libraries that shape a frame."""
    global _CODE_VERSION
    if _CODE_VERSION is not None:
        return _CODE_VERSION
    import numpy as np
    import pandas as pd
    import pyarrow as pa

    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = hashlib.sha256()
    for path in sorted(glob.glob(os.path.join(package, "**", "*.py"), recursive=True)):
        h.update(os.path.relpath(path, package).encode())
        with open(path, "rb") as fh:
            h.update(hashlib.sha256(fh.read()).digest())
    h.update(json.dumps([FORMAT, sys.version, pd.__version__, np.__version__, pa.__version__]).encode())
    _CODE_VERSION = h.hexdigest()
    return _CODE_VERSION


#: Settings that change nothing in a result (where the cache lives, how big it
#: may grow) or that are secrets (only whether they are set matters).
_ENV_IGNORED = {"PWB_CACHE", "PWB_CACHE_DIR", "PWB_PREPARED_CACHE_MAX_GB", "PWB_API_CACHE_MAX_GB",
                "PWB_API_WORKERS", "PWB_READ_MEMO_MB", "PWB_OPTIONS_CACHE", "PWB_OPTIONS_CACHE_MAX_GB"}
_ENV_SECRET = {"PWB_API_KEY"}


def _environment():
    env = {}
    for name, value in os.environ.items():
        if not name.startswith("PWB_") or name in _ENV_IGNORED:
            continue
        env[name] = bool(value) if name in _ENV_SECRET else value
    for name in ("HF_HUB_OFFLINE", "HF_ENDPOINT"):
        if os.getenv(name):
            env[name] = os.getenv(name)
    return sorted(env.items())


def _call_key(name: str, bound: inspect.BoundArguments) -> tuple[str, str]:
    """``(hash, description)`` of a call."""
    args = [[k, _canon(v)] for k, v in bound.arguments.items()]
    desc = json.dumps([name, args, _environment(), code_version()], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(desc.encode()).hexdigest(), desc


def _content_key(call_key: str, deps) -> str:
    text = json.dumps([call_key, deps], separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Resolution of a recorded dependency                                         #
# --------------------------------------------------------------------------- #
def _resolve(kind: str, name: str):
    """The revision this process reads ``name`` at, or ``None``."""
    with _LOCK:
        if (kind, name) in _RESOLVED:
            return _RESOLVED[(kind, name)]
    try:
        from . import _api_file_index, _hub_snapshot

        if kind == "hub":
            sha, _ = _hub_snapshot(name, os.getenv("HF_ACCESS_TOKEN"))
            return sha  # _hub_snapshot notes it
        if kind == "api":
            index = _api_file_index(name)
            sha = index[0] if index else None
            note_revision("api", name, sha)
            return sha
        if kind == "table":
            loader = _TABLE_LOADERS.get(name)
            if loader is None:
                return None
            loader()
            with _LOCK:
                return _RESOLVED.get((kind, name))
    except Exception:  # noqa: BLE001 - unresolvable: not a hit
        return None
    return None


def _dependencies():
    """The process's revisions as a sorted list, or ``None`` if one is unknown."""
    with _LOCK:
        items = sorted(_RESOLVED.items())
    if not items or any(sha is None for _, sha in items):
        return None
    return [[kind, name, sha] for (kind, name), sha in items]


# --------------------------------------------------------------------------- #
# Files                                                                       #
# --------------------------------------------------------------------------- #
def _data_path(root, content_key):
    return os.path.join(root, "data", content_key[:2], content_key + ".pwbc")


def _manifest_path(root, call_key):
    return os.path.join(root, "manifests", call_key[:2], call_key + ".json")


def _atomic_write(path: str, write) -> None:
    """``write(fh)`` into a temporary file next to ``path``, then rename it into place."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            write(fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _pad(n: int) -> int:
    return (-n) % _ALIGN


def _dump(path: str, value, header: dict) -> int:
    buffers = []
    main = pickle.dumps(value, protocol=5, buffer_callback=buffers.append)
    raws = [b.raw() for b in buffers]
    head = dict(header, main_len=len(main), buffers=[r.nbytes for r in raws])
    head_bytes = json.dumps(head).encode()
    written = [0]

    def write(fh):
        def put(data):
            fh.write(data)
            written[0] += len(data) if isinstance(data, (bytes, bytearray)) else memoryview(data).nbytes

        put(_MAGIC)
        put(struct.pack("<Q", len(head_bytes)))
        put(head_bytes)
        put(b"\0" * _pad(written[0]))
        put(main)
        for raw in raws:
            put(b"\0" * _pad(written[0]))
            put(raw)
        put(_END)

    _atomic_write(path, write)
    return written[0]


def _load(path: str):
    """``(value, header)`` of an entry; raises on anything malformed."""
    with open(path, "rb") as fh:
        size = os.fstat(fh.fileno()).st_size
        if size < len(_MAGIC) + 8 + len(_END):
            raise ValueError("truncated")
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_COPY)
    view = memoryview(mm)
    if bytes(view[: len(_MAGIC)]) != _MAGIC or bytes(view[size - len(_END):]) != _END:
        raise ValueError("bad magic")
    (head_len,) = struct.unpack("<Q", view[len(_MAGIC): len(_MAGIC) + 8])
    offset = len(_MAGIC) + 8
    header = json.loads(bytes(view[offset: offset + head_len]))
    if header.get("format") != FORMAT:
        raise ValueError("format")
    offset += head_len
    offset += _pad(offset)
    main = view[offset: offset + header["main_len"]]
    offset += header["main_len"]
    buffers = []
    for n in header["buffers"]:
        offset += _pad(offset)
        buffers.append(view[offset: offset + n])
        offset += n
    if offset + len(_END) != size:
        raise ValueError("size mismatch")
    return pickle.loads(main, buffers=buffers), header


def _read_manifest(root, call_key) -> list:
    try:
        with open(_manifest_path(root, call_key), encoding="utf-8") as fh:
            variants = json.load(fh)["variants"]
        return [[tuple(d) for d in v] for v in variants]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _write_manifest(root, call_key, variant) -> None:
    variants = [variant] + [v for v in _read_manifest(root, call_key) if v != variant]
    payload = json.dumps({"variants": [[list(d) for d in v] for v in variants[:_MAX_VARIANTS]]}).encode()
    _atomic_write(_manifest_path(root, call_key), lambda fh: fh.write(payload))


def _evict(root, keep: str) -> None:
    try:
        cap = float(os.getenv("PWB_PREPARED_CACHE_MAX_GB", _MAX_GB_DEFAULT)) * 1024**3
    except ValueError:
        cap = _MAX_GB_DEFAULT * 1024**3
    entries = []
    for path in glob.glob(os.path.join(root, "data", "*", "*.pwbc")):
        try:
            st = os.stat(path)
        except OSError:
            continue
        entries.append((st.st_mtime, st.st_size, path))
    total = sum(size for _, size, _ in entries)
    for _, size, path in sorted(entries):
        if total <= cap:
            break
        if path == keep:
            continue
        try:
            os.unlink(path)
            total -= size
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Side effects                                                                #
# --------------------------------------------------------------------------- #
class _Tee(io.TextIOBase):
    """Writes through to the stream it wraps and keeps a copy."""

    def __init__(self, inner):
        self._inner = inner
        self.parts = []

    def write(self, text):
        self.parts.append(text)
        return self._inner.write(text)

    def flush(self):
        return self._inner.flush()

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _Recorded:
    """Prints of a computation, and the warnings ``pwb_toolbox`` code raised in it.

    The stack levels of those warnings already count the cache's wrapper, so
    they point at the caller of ``load_dataset``; a replayed one does too."""

    def __enter__(self):
        self.warnings = []
        self._stdout = sys.stdout
        self._tee = _Tee(sys.stdout)
        sys.stdout = self._tee
        self._warn = warnings.warn
        recorder = self

        def warn(message, category=None, stacklevel=1, *args, **kwargs):
            cat = category if category is not None else (
                type(message) if isinstance(message, Warning) else UserWarning)
            caller = sys._getframe(1).f_globals.get("__name__", "")
            if str(caller).startswith("pwb_toolbox"):
                recorder.warnings.append((cat.__module__, cat.__qualname__, str(message)))
            return recorder._warn(message, category, stacklevel + 1, *args, **kwargs)

        warnings.warn = warn
        return self

    def __exit__(self, *exc):
        warnings.warn = self._warn
        if sys.stdout is self._tee:
            sys.stdout = self._stdout
        self.stdout = "".join(self._tee.parts)
        return False


def _replay(header) -> None:
    text = header.get("stdout") or ""
    if text:
        sys.stdout.write(text)
    for module, qualname, message in header.get("warnings") or []:
        category = sys.modules.get(module)
        for part in qualname.split("."):
            category = getattr(category, part, None)
        if not (isinstance(category, type) and issubclass(category, Warning)):
            category = UserWarning
        warnings.warn(message, category, stacklevel=3)


# --------------------------------------------------------------------------- #
# The decorator                                                               #
# --------------------------------------------------------------------------- #
def _globally_off() -> bool:
    return not enabled() or bool(_DEGRADED) or bool(os.getenv("PWB_PIT_UNIVERSE_DIR"))


def cached(name: str, skip=None):
    """Cache the outermost call of ``fn`` on disk (see the module docstring).

    ``skip(arguments)`` -> True keeps a call out of the cache.
    """

    def decorate(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            depth = _DEPTH.get()
            key = None
            if not depth and not _globally_off():
                try:
                    bound = signature.bind(*args, **kwargs)
                    bound.apply_defaults()
                    if skip is None or not skip(bound.arguments):
                        key = _call_key(name, bound)
                except _Uncacheable:
                    key = None
                except TypeError:
                    key = None  # a bad call: let the function raise its own error
            if key is None:
                if not depth:
                    stats["bypassed"] += 1
                token = _DEPTH.set(depth + 1)
                try:
                    return fn(*args, **kwargs)
                finally:
                    _DEPTH.reset(token)

            call_key, desc = key
            root = cache_root()
            found = _lookup(root, call_key)
            if found is not None:
                value, header = found
                stats["hits"] += 1
                stats["seconds_saved_estimate"] += float(header.get("seconds") or 0.0)
                _replay(header)
                return value

            stats["misses"] += 1
            token = _DEPTH.set(depth + 1)
            started = time.perf_counter()
            try:
                with _Recorded() as recorded:
                    value = fn(*args, **kwargs)
            finally:
                _DEPTH.reset(token)
            seconds = time.perf_counter() - started
            deps = _dependencies()
            if deps is not None and not _globally_off():
                _store(root, call_key, desc, deps, value, recorded, seconds)
            return value

        wrapper.__wrapped_uncached__ = fn
        return wrapper

    return decorate


def _lookup(root, call_key):
    for variant in _read_manifest(root, call_key):
        deps = []
        for kind, dep in variant:
            sha = _resolve(kind, dep)
            if sha is None:
                break
            deps.append([kind, dep, sha])
        else:
            if _DEGRADED:
                return None  # resolving a table just found it unreadable
            path = _data_path(root, _content_key(call_key, deps))
            if not os.path.exists(path):
                continue
            try:
                value, header = _load(path)
            except Exception:  # noqa: BLE001 - a bad file is a miss, and goes
                stats["errors"] += 1
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            try:
                os.utime(path, None)
            except OSError:
                pass
            return value, header
    return None


def _store(root, call_key, desc, deps, value, recorded, seconds) -> None:
    variant = [(kind, dep) for kind, dep, _ in deps]
    path = _data_path(root, _content_key(call_key, deps))
    header = {
        "format": FORMAT,
        "call": desc,
        "deps": deps,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(seconds, 3),
        "stdout": recorded.stdout,
        "warnings": recorded.warnings,
    }
    try:
        _dump(path, value, header)
        _write_manifest(root, call_key, variant)
        stats["stored"] += 1
        _evict(root, keep=path)
    except Exception as exc:  # noqa: BLE001 - a cache that cannot write is only slower
        stats["errors"] += 1
        print(f"[cache] not stored ({type(exc).__name__}: {exc})")
