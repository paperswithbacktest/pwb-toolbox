"""Tolerant readers for Grok's undocumented chat payloads.

The endpoints behind grok.com are internal: field names differ between builds
and xAI changes them without notice. Nothing here assumes a single spelling.
Every accessor takes candidate keys and returns the first one actually present,
and callers keep the raw payload alongside the parsed form, so a wrong guess
here degrades the rendered Markdown without ever losing a message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Sequence

ID_KEYS = ("conversationId", "conversation_id", "id", "uuid", "conversationUuid")
TITLE_KEYS = ("title", "name", "summary", "topic", "subject")
CREATED_KEYS = (
    "createTime",
    "create_time",
    "createdAt",
    "created_at",
    "created",
    "timestamp",
)
UPDATED_KEYS = (
    "modifyTime",
    "modify_time",
    "updateTime",
    "updatedAt",
    "updated_at",
    "updated",
)

# Keys whose value is the list of conversations in a listing response.
CONVERSATION_LIST_KEYS = ("conversations", "items", "data", "results", "records")
# Keys that hold a conversation's metadata one level down, as the official
# export does with ``{"conversation": {...}, "responses": [...]}``.
CONVERSATION_WRAPPER_KEYS = ("conversation", "conv", "chat", "thread")
# Keys whose value is the list of turns inside a single conversation.
MESSAGE_LIST_KEYS = (
    "responses",
    "messages",
    "turns",
    "nodes",
    "responseNodes",
    "response_nodes",
    "history",
    "items",
)
# Keys that carry the next page token in a listing response.
CURSOR_KEYS = (
    "nextPageToken",
    "next_page_token",
    "nextCursor",
    "next_cursor",
    "cursor",
    "pageToken",
)

TEXT_KEYS = (
    "message",
    "text",
    "content",
    "response",
    "fullMessage",
    "full_message",
    "prompt",
    "answer",
    "body",
)
ROLE_KEYS = (
    "sender",
    "role",
    "author",
    "responseType",
    "response_type",
    "speaker",
    "type",
)
BOOL_ROLE_KEYS = ("isUser", "is_user", "fromUser", "from_user", "isHuman", "is_human")
# Keys that wrap the real turn one level down, as the official export does with
# ``{"response": {...}, "share_link": ...}``.
TURN_WRAPPER_KEYS = ("response", "node", "turn", "message", "data", "item")
# Timestamps arrive as MongoDB extended JSON ({"$date": {"$numberLong": ...}})
# or as a protobuf Timestamp ({"seconds": ...}) as well as plain scalars.
NESTED_TIME_KEYS = (
    "$date",
    "$numberLong",
    "$numberDouble",
    "$numberInt",
    "seconds",
    "epochMillis",
    "epoch_millis",
    "value",
)

# Checked as substrings: real values look like "RESPONSE_TYPE_HUMAN", not "human".
_USER_TOKENS = ("human", "user", "you", "self", "query")
_ASSISTANT_TOKENS = ("assistant", "grok", "model", "bot", "response", "answer", "ai")

_MAX_TEXT_DEPTH = 6
_SUBSECOND_RE = re.compile(r"(\.\d{6})\d+")


def pick(payload: Any, keys: Sequence[str], default: Any = None) -> Any:
    """Return the first key in ``keys`` present and non-empty on ``payload``."""
    if not isinstance(payload, dict):
        return default
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return default


def pick_list(payload: Any, keys: Sequence[str]) -> list | None:
    """Return the first key in ``keys`` whose value on ``payload`` is a list."""
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return None


def to_datetime(value: Any, _depth: int = 0) -> datetime | None:
    """Best-effort UTC datetime from ISO-8601, epoch seconds, or epoch millis.

    Also unwraps the nested forms these payloads use, notably MongoDB extended
    JSON: ``{"$date": {"$numberLong": "1785198572458"}}``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, dict):
        if _depth >= 4:
            return None
        for key in NESTED_TIME_KEYS:
            if key in value:
                return to_datetime(value[key], _depth + 1)
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        # Seconds that far out land past year 5138; it is really milliseconds.
        if abs(seconds) > 1e11:
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.lstrip("-").isdigit():
            return to_datetime(int(text))
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        # 3.10's fromisoformat rejects more than six fractional digits.
        text = _SUBSECOND_RE.sub(r"\1", text)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def conversation_meta(payload: Any) -> dict:
    """Flatten a wrapped conversation so its metadata sits at the top level.

    ``{"conversation": {"id": ..., "title": ...}, "responses": [...]}`` becomes
    a single dict carrying the id, the title and the turn list together. Outer
    keys win, so a wrapper that also sets a field is not overwritten.
    """
    if not isinstance(payload, dict):
        return {}
    for key in CONVERSATION_WRAPPER_KEYS:
        inner = payload.get(key)
        if isinstance(inner, dict):
            outer = {k: v for k, v in payload.items() if k != key}
            return {**inner, **outer}
    return payload


def unwrap_turn(payload: Any) -> Any:
    """Return the inner turn when a payload only wraps one.

    The official export nests each turn as ``{"response": {...}, "share_link":
    ...}``, so role and timestamp live a level below where they are looked for.
    A payload that already carries role information is returned untouched.
    """
    if not isinstance(payload, dict):
        return payload
    if any(key in payload for key in ROLE_KEYS + BOOL_ROLE_KEYS):
        return payload
    for key in TURN_WRAPPER_KEYS:
        inner = payload.get(key)
        if isinstance(inner, dict) and any(
            candidate in inner for candidate in ROLE_KEYS + BOOL_ROLE_KEYS
        ):
            return inner
    return payload


def normalize_role(payload: Any) -> str:
    """Classify a turn as ``user``, ``assistant``, or ``unknown``."""
    if isinstance(payload, dict):
        for key in BOOL_ROLE_KEYS:
            value = payload.get(key)
            if isinstance(value, bool):
                return "user" if value else "assistant"

    raw = pick(payload, ROLE_KEYS)
    if isinstance(raw, dict):
        raw = pick(raw, ("role", "name", "type"))
    token = str(raw or "").strip().lower()
    if not token:
        return "unknown"
    # User tokens win: a value like "RESPONSE_TYPE_HUMAN" matches both sets.
    if any(candidate in token for candidate in _USER_TOKENS):
        return "user"
    if any(candidate in token for candidate in _ASSISTANT_TOKENS):
        return "assistant"
    return "unknown"


def extract_text(payload: Any, _depth: int = 0) -> str:
    """Pull the human-readable body out of a turn, descending nested shapes."""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict) or _depth >= _MAX_TEXT_DEPTH:
        return ""
    for key in TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            nested = extract_text(value, _depth + 1)
            if nested:
                return nested
        if isinstance(value, list):
            parts = [extract_text(item, _depth + 1) for item in value]
            joined = "\n\n".join(part for part in parts if part.strip())
            if joined:
                return joined
    return ""


@dataclass
class Message:
    """One turn of a conversation."""

    role: str
    text: str
    created: datetime | None = None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class Conversation:
    """A Grok conversation and its turns."""

    id: str
    title: str = ""
    created: datetime | None = None
    updated: datetime | None = None
    messages: list[Message] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        return f"Untitled {self.id[:8]}" if self.id else "Untitled"


def parse_message(payload: Any) -> Message:
    """Build a :class:`Message` from one turn payload."""
    if not isinstance(payload, dict):
        return Message(role="unknown", text=str(payload or ""), raw={})
    inner = unwrap_turn(payload)
    return Message(
        role=normalize_role(inner),
        text=extract_text(inner),
        created=to_datetime(pick(inner, CREATED_KEYS)),
        # Keep the payload as it arrived, wrapper and all.
        raw=payload,
    )


def _message_payloads(payload: Any) -> list:
    """Locate the turn list inside a conversation payload."""
    turns = pick_list(payload, MESSAGE_LIST_KEYS)
    if turns is not None:
        return turns
    if isinstance(payload, dict):
        # Some builds wrap the turns one level down, e.g. {"conversation": {...}}.
        for value in payload.values():
            if isinstance(value, dict):
                nested = pick_list(value, MESSAGE_LIST_KEYS)
                if nested is not None:
                    return nested
    return []


def parse_conversation(payload: Any, detail: Any = None) -> Conversation:
    """Build a :class:`Conversation` from a listing entry plus optional detail.

    ``detail`` is the per-conversation response that carries the turns; when it
    is omitted the turns are looked for on ``payload`` itself.
    """
    payload = payload if isinstance(payload, dict) else {}
    meta = conversation_meta(payload)
    turn_source = detail if detail is not None else meta
    messages = [parse_message(item) for item in _message_payloads(turn_source)]
    # Newest-first listings are common; render oldest-first when times allow.
    if all(message.created is not None for message in messages) and len(messages) > 1:
        messages.sort(key=lambda message: message.created)

    raw: dict = {"listing": payload}
    if detail is not None:
        raw["detail"] = detail

    return Conversation(
        id=str(pick(meta, ID_KEYS, "") or ""),
        title=str(pick(meta, TITLE_KEYS, "") or ""),
        created=to_datetime(pick(meta, CREATED_KEYS)),
        updated=to_datetime(pick(meta, UPDATED_KEYS)),
        messages=messages,
        raw=raw,
    )


def iter_conversation_payloads(response: Any) -> Iterator[dict]:
    """Yield the conversation entries out of a listing response."""
    if isinstance(response, list):
        entries: list = response
    else:
        entries = pick_list(response, CONVERSATION_LIST_KEYS) or []
    for entry in entries:
        if isinstance(entry, dict):
            yield entry


def next_cursor(response: Any) -> str | None:
    """Return the pagination token from a listing response, if any."""
    if not isinstance(response, dict):
        return None
    for container in (response, response.get("pagination"), response.get("page")):
        token = pick(container, CURSOR_KEYS)
        if isinstance(token, str) and token:
            return token
    return None
