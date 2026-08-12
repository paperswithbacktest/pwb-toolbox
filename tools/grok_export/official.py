"""Reading the official xAI account data export.

The sanctioned route is to request a data download from accounts.x.ai/data and
wait for the archive. Its internal layout is not documented either, so instead
of assuming a nesting this module walks the whole JSON tree and picks out
anything shaped like a conversation. That survives a re-organised dump in a way
a hard-coded path would not.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import schema
from .schema import Conversation

_MAX_WALK_DEPTH = 12
_UNDATED = datetime.max.replace(tzinfo=timezone.utc)


def _looks_like_message(value: Any) -> bool:
    """True when a dict plausibly represents a single conversation turn."""
    if not isinstance(value, dict):
        return False
    # Turns in the official export are wrapped, putting the role a level down.
    inner = schema.unwrap_turn(value)
    has_role = any(key in inner for key in schema.ROLE_KEYS + schema.BOOL_ROLE_KEYS)
    has_text = bool(schema.extract_text(inner))
    return has_role and has_text


def _message_list(value: Any) -> list | None:
    """The turn list on a conversation-shaped dict, if it has one."""
    turns = schema.pick_list(value, schema.MESSAGE_LIST_KEYS)
    if turns is None:
        return None
    dicts = [item for item in turns if isinstance(item, dict)]
    if not dicts:
        return None
    # One convincing turn is enough; dumps mix in metadata-only entries.
    if any(_looks_like_message(item) for item in dicts):
        return turns
    return None


def _looks_like_conversation(value: Any) -> bool:
    """True when a dict carries conversation metadata and a list of turns."""
    if not isinstance(value, dict):
        return False
    if _message_list(value) is None:
        return False
    # The id and title may sit under a wrapper key alongside the turns.
    meta = schema.conversation_meta(value)
    identified = schema.pick(meta, schema.ID_KEYS) is not None
    titled = schema.pick(meta, schema.TITLE_KEYS) is not None
    return identified or titled


def walk_conversations(payload: Any, _depth: int = 0) -> Iterator[dict]:
    """Yield every conversation-shaped dict anywhere in a decoded dump."""
    if _depth > _MAX_WALK_DEPTH:
        return
    if isinstance(payload, dict):
        if _looks_like_conversation(payload):
            yield payload
            return  # Turns live below; do not re-yield them as conversations.
        for value in payload.values():
            yield from walk_conversations(value, _depth + 1)
    elif isinstance(payload, list):
        for item in payload:
            yield from walk_conversations(item, _depth + 1)


def _decode(text: str) -> Any:
    """Decode JSON, falling back to JSON Lines."""
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records or None


def iter_payloads(source: Path) -> Iterator[tuple[str, Any]]:
    """Yield ``(name, decoded)`` for every JSON document in ``source``.

    ``source`` may be a ``.zip`` archive, a directory, or a single JSON/JSONL
    file — whichever form the download happens to arrive in.
    """
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.suffix.lower() in (".json", ".jsonl") and path.is_file():
                decoded = _decode(path.read_text(encoding="utf-8", errors="replace"))
                if decoded is not None:
                    yield str(path.relative_to(source)), decoded
        return

    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if not info.filename.lower().endswith((".json", ".jsonl")):
                    continue
                with archive.open(info) as handle:
                    decoded = _decode(handle.read().decode("utf-8", errors="replace"))
                if decoded is not None:
                    yield info.filename, decoded
        return

    decoded = _decode(source.read_text(encoding="utf-8", errors="replace"))
    if decoded is not None:
        yield source.name, decoded


def load_conversations(source: Path) -> list[Conversation]:
    """Parse every conversation out of an official export, de-duplicated by id."""
    conversations: list[Conversation] = []
    seen: set[str] = set()

    for _, payload in iter_payloads(source):
        for entry in walk_conversations(payload):
            conversation = schema.parse_conversation(entry)
            key = conversation.id
            if key:
                if key in seen:
                    continue
                seen.add(key)
            conversations.append(conversation)

    # Undated conversations sort last; a plain `or None` key would compare
    # None against None and raise.
    conversations.sort(key=lambda item: item.created or _UNDATED)
    return conversations
