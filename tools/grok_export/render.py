"""Writing exported conversations to disk as raw JSON and readable Markdown.

Two artefacts per export, with different jobs. ``raw/`` holds each payload
verbatim so nothing is lost to a misread field and a later run can re-render
without touching the network; ``markdown/`` is the copy meant to be read.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .schema import Conversation, Message

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 60

ROLE_LABELS = {"user": "You", "assistant": "Grok", "unknown": "Unknown"}


def slugify(text: str) -> str:
    """Filesystem-safe, lowercase-hyphenated form of ``text``."""
    slug = _SLUG_STRIP_RE.sub("-", (text or "").lower()).strip("-")
    return slug[:_SLUG_MAX].strip("-")


def conversation_stem(conversation: Conversation) -> str:
    """Sortable, collision-resistant filename stem: date, title, id fragment."""
    parts = []
    stamp = conversation.created or conversation.updated
    if stamp:
        parts.append(stamp.strftime("%Y-%m-%d"))
    slug = slugify(conversation.title)
    if slug:
        parts.append(slug)
    suffix = (conversation.id or "").replace("-", "")[:8]
    if suffix:
        parts.append(suffix)
    return "-".join(parts) or "conversation"


def _yaml_value(value: str) -> str:
    """Quote a scalar for YAML. JSON string syntax is valid YAML."""
    return json.dumps(value, ensure_ascii=False)


def _stamp(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def render_markdown(conversation: Conversation) -> str:
    """Render one conversation as Markdown with YAML frontmatter."""
    lines = [
        "---",
        f"title: {_yaml_value(conversation.title or 'Untitled')}",
        f"grok_conversation_id: {_yaml_value(conversation.id)}",
    ]
    if conversation.created:
        lines.append(f"created: {_yaml_value(_stamp(conversation.created))}")
    if conversation.updated:
        lines.append(f"updated: {_yaml_value(_stamp(conversation.updated))}")
    lines.append(f"messages: {len(conversation.messages)}")
    lines.append("source: grok.com")
    lines.append("---")
    lines.append("")
    lines.append(f"# {conversation.title or 'Untitled conversation'}")
    lines.append("")

    if not conversation.messages:
        lines.append("_No messages were returned for this conversation._")
        lines.append("")

    for message in conversation.messages:
        lines.append(f"## {ROLE_LABELS.get(message.role, message.role.title())}")
        if message.created:
            lines.append("")
            lines.append(f"*{_stamp(message.created)}*")
        lines.append("")
        lines.append(message.text.strip() or "_(empty message)_")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """A path under ``directory`` that does not collide with an existing file."""
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def write_raw(directory: Path, conversation_id: str, payload: object) -> Path:
    """Archive a payload verbatim under ``directory``, keyed by conversation id."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(conversation_id) or 'conversation'}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def raw_path(directory: Path, conversation_id: str) -> Path:
    """Where :func:`write_raw` would put ``conversation_id`` (no I/O)."""
    return directory / f"{slugify(conversation_id) or 'conversation'}.json"


def write_markdown(directory: Path, conversation: Conversation) -> Path:
    """Write one conversation's Markdown, avoiding filename collisions."""
    directory.mkdir(parents=True, exist_ok=True)
    path = _unique_path(directory, conversation_stem(conversation), ".md")
    path.write_text(render_markdown(conversation), encoding="utf-8")
    return path


def write_index(directory: Path, conversations: Iterable[Conversation]) -> Path:
    """Write a compact index of everything exported."""
    directory.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "id": conversation.id,
            "title": conversation.title,
            "created": _stamp(conversation.created),
            "updated": _stamp(conversation.updated),
            "messages": len(conversation.messages),
        }
        for conversation in conversations
    ]
    path = directory / "index.json"
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
