"""Storage and validation for the shared karaoke leaderboard.

Deliberately free of HTTP so the rules can be exercised without binding a
socket -- the suite must not need the network.

Nothing the client sends is trusted beyond its shape: text is length-capped
and stripped of control characters, numbers are range-clamped, and the
timestamp is assigned here rather than read from the request, so a client
cannot backdate itself to the top of a tie.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone

MAX_ENTRIES = 500
MAX_NAME = 24
MAX_TITLE = 80
MAX_RANK = 32
MAX_CODE = 8


class ValidationError(ValueError):
    """A submitted run was malformed. Carries a message safe to return."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(raw, field, limit, default=None):
    value = raw.get(field, default)
    if value is None:
        if default is None:
            raise ValidationError(f"{field} is required")
        value = default
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    # control characters would corrupt the rendered board
    value = "".join(ch for ch in value if ch >= " " and ch != "\x7f").strip()
    if not value:
        if default is None:
            raise ValidationError(f"{field} is required")
        value = default
    return value[:limit]


def _int(raw, field, lo, hi, default=None):
    value = raw.get(field, default)
    if value is None:
        raise ValidationError(f"{field} is required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number")
    value = int(value)
    if value < lo or value > hi:
        raise ValidationError(f"{field} must be between {lo} and {hi}")
    return value


def clean_entry(raw) -> dict:
    """Validate one submitted run and return the record to store."""
    if not isinstance(raw, dict):
        raise ValidationError("expected an object")
    part = raw.get("part", "a")
    if part not in ("a", "b"):
        part = "a"
    return {
        "score": _int(raw, "score", 0, 100),
        "title": _text(raw, "title", MAX_TITLE),
        "name": _text(raw, "name", MAX_NAME, default="You"),
        "code": _text(raw, "code", MAX_CODE, default="---"),
        "rank": _text(raw, "rank", MAX_RANK, default=""),
        "notes": _int(raw, "notes", 0, 100000, default=0),
        "hit": _int(raw, "hit", 0, 100000, default=0),
        "tempo": _int(raw, "tempo", 25, 400, default=100),
        "duet": bool(raw.get("duet", False)),
        "part": part,
        # assigned here, never taken from the client
        "at": _now_iso(),
    }


def _order(rows):
    """Best score first; among equals the earlier run keeps the higher place."""
    return sorted(rows, key=lambda e: (-e.get("score", 0), e.get("at", "")))


class Board:
    """A leaderboard persisted as a JSON file."""

    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.Lock()

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, OSError):
            # a truncated or hand-mangled file should not take the server down
            return []
        if not isinstance(rows, list):
            return []
        return [r for r in rows if isinstance(r, dict) and "score" in r]

    def _write(self, rows):
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        os.makedirs(directory, exist_ok=True)
        # write-then-replace, so a crash mid-write cannot leave a half file
        handle, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def add(self, raw) -> dict:
        entry = clean_entry(raw)
        with self._lock:
            rows = _order(self._read() + [entry])[:MAX_ENTRIES]
            self._write(rows)
        return entry

    def top(self, limit=20):
        limit = max(1, min(int(limit), 100))
        with self._lock:
            return _order(self._read())[:limit]

    def clear(self):
        with self._lock:
            self._write([])
