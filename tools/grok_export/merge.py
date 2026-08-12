"""Grouping near-duplicate conversations and merging each group into one file.

Chat histories accumulate the same thread several times over: the identical
question re-asked months later, or one topic picked up across four sittings.
This finds those and writes one document per topic, ordered by date, so the
thread reads as a single conversation.

Similarity is TF-IDF cosine over title and message tokens, with titles weighted
because they are short and deliberate. Clustering is single-link, so a chain of
related conversations lands together even when the ends do not resemble each
other directly. Everything is stdlib — this stays runnable as a plain script.

Originals are never touched. Merged files are written alongside them.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from . import render
from .schema import Conversation

# Common English plus the filler that dominates chat prompts ("you are a ...
# expert", "give me", "create me"). Left in, these make every conversation look
# alike and collapse the whole export into one cluster.
STOPWORDS = frozenset("""
    a about after all also am an and any are as at be because been before being
    but by can cant could did do does doing dont down each few for from further
    get give got had has have having he her here hers him his how i if in into
    is it its itself just like me more most my no nor not now of off on once
    one only or other our out over own same she should so some such than that
    the their them then there these they this those through to too under until
    up very was we were what when where which while who whom why will with
    would you your yours create created creating make making made need needs
    want wants help helps expert professional please tell show explain write
    list give given best good new use using used thing things way ways lot
    know let see say said also may might must shall
    """.split())

_TOKEN_RE = re.compile(r"[a-z][a-z0-9'-]{1,}")
_TITLE_WEIGHT = 3
_MIN_TOKEN_DOCS = 1

# Tuned on a real 29-conversation export. Below ~0.22 single-link chaining
# starts pulling unrelated matters together through shared vocabulary (two
# different legal threads merging on general court words); above ~0.30 genuine
# continuations of the same topic stop matching.
DEFAULT_THRESHOLD = 0.26


def tokenize(text: str) -> list[str]:
    """Lowercase content words, stopwords and one-character noise removed."""
    return [
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if token not in STOPWORDS and len(token) > 2
    ]


def conversation_tokens(conversation: Conversation) -> Counter:
    """Token counts for a conversation, with the title weighted up."""
    counts = Counter(tokenize(conversation.title))
    for token in list(counts):
        counts[token] *= _TITLE_WEIGHT
    for message in conversation.messages:
        counts.update(tokenize(message.text))
    return counts


def content_hash(conversation: Conversation) -> str:
    """Stable digest of a conversation's message bodies, order-independent."""
    bodies = sorted((message.text or "").strip() for message in conversation.messages)
    return hashlib.sha256("\n".join(bodies).encode("utf-8")).hexdigest()


def tfidf(documents: Sequence[Counter]) -> list[dict[str, float]]:
    """L2-normalised TF-IDF vectors for already-tokenised documents."""
    total = len(documents)
    if not total:
        return []
    frequency: Counter = Counter()
    for document in documents:
        frequency.update(document.keys())

    vectors: list[dict[str, float]] = []
    for document in documents:
        vector: dict[str, float] = {}
        for token, count in document.items():
            if frequency[token] < _MIN_TOKEN_DOCS:
                continue
            idf = math.log((1 + total) / (1 + frequency[token])) + 1.0
            vector[token] = (1.0 + math.log(count)) * idf
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm:
            vector = {token: value / norm for token, value in vector.items()}
        vectors.append(vector)
    return vectors


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    """Cosine similarity of two normalised sparse vectors."""
    if len(right) < len(left):
        left, right = right, left
    return sum(value * right.get(token, 0.0) for token, value in left.items())


class _Union:
    """Union-find, so related conversations merge transitively."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left, right = self.find(left), self.find(right)
        if left != right:
            self._parent[right] = left


@dataclass
class Group:
    """One topic: the conversations that belong to it, oldest first."""

    conversations: list[Conversation] = field(default_factory=list)
    duplicates: list[Conversation] = field(default_factory=list)

    @property
    def title(self) -> str:
        """Label the group by its meatiest conversation."""
        if not self.conversations:
            return "Untitled"
        richest = max(self.conversations, key=lambda c: len(c.messages))
        return richest.title or richest.display_title

    @property
    def span(self) -> tuple[datetime | None, datetime | None]:
        stamps = [c.created for c in self.conversations if c.created]
        return (min(stamps), max(stamps)) if stamps else (None, None)

    @property
    def message_count(self) -> int:
        return sum(len(c.messages) for c in self.conversations)


def _dedupe_exact(
    conversations: Sequence[Conversation],
) -> tuple[list[Conversation], dict[str, list[Conversation]]]:
    """Split off byte-identical repeats, keeping the earliest of each."""
    by_hash: dict[str, list[Conversation]] = {}
    for conversation in conversations:
        by_hash.setdefault(content_hash(conversation), []).append(conversation)

    kept: list[Conversation] = []
    dropped: dict[str, list[Conversation]] = {}
    for digest, group in by_hash.items():
        group.sort(
            key=lambda c: (
                c.created is None,
                c.created or datetime.max.replace(tzinfo=timezone.utc),
            )
        )
        kept.append(group[0])
        if len(group) > 1:
            dropped[group[0].id] = group[1:]
    return kept, dropped


def group_conversations(
    conversations: Sequence[Conversation], threshold: float = DEFAULT_THRESHOLD
) -> list[Group]:
    """Cluster conversations by topic, collapsing exact duplicates first.

    Returns every conversation exactly once, in groups ordered by their earliest
    date. Singletons come back as one-member groups.
    """
    if not conversations:
        return []

    kept, duplicates = _dedupe_exact(conversations)
    vectors = tfidf([conversation_tokens(c) for c in kept])

    union = _Union(len(kept))
    for i in range(len(kept)):
        for j in range(i + 1, len(kept)):
            if cosine(vectors[i], vectors[j]) >= threshold:
                union.union(i, j)

    buckets: dict[int, Group] = {}
    for index, conversation in enumerate(kept):
        group = buckets.setdefault(union.find(index), Group())
        group.conversations.append(conversation)
        group.duplicates.extend(duplicates.get(conversation.id, []))

    result = list(buckets.values())
    undated = datetime.max.replace(tzinfo=timezone.utc)
    for group in result:
        group.conversations.sort(key=lambda c: c.created or undated)
    result.sort(key=lambda g: g.conversations[0].created or undated)
    return result


def render_group(group: Group) -> str:
    """Render one group as a single Markdown document."""
    start, end = group.span
    lines = [
        "---",
        f"title: {render._yaml_value(group.title)}",
        f"merged_from: {len(group.conversations)}",
        f"messages: {group.message_count}",
    ]
    if start:
        lines.append(f"span_start: {render._yaml_value(start.isoformat())}")
    if end:
        lines.append(f"span_end: {render._yaml_value(end.isoformat())}")
    lines.append("source_conversations:")
    for conversation in group.conversations:
        lines.append(f"  - id: {render._yaml_value(conversation.id)}")
        lines.append(f"    title: {render._yaml_value(conversation.title)}")
    if group.duplicates:
        lines.append(f"exact_duplicates_collapsed: {len(group.duplicates)}")
    lines.append("source: grok.com")
    lines.append("---")
    lines.append("")
    lines.append(f"# {group.title}")
    lines.append("")

    summary = f"_Merged from {len(group.conversations)} conversation(s)"
    if start and end and start.date() != end.date():
        summary += f", {start.date()} to {end.date()}"
    summary += f", {group.message_count} messages._"
    lines.append(summary)
    if group.duplicates:
        titles = ", ".join(sorted({c.title or c.id for c in group.duplicates}))
        lines.append("")
        lines.append(
            f"_{len(group.duplicates)} exact duplicate(s) collapsed: {titles}._"
        )
    lines.append("")

    for conversation in group.conversations:
        date = (
            conversation.created.date().isoformat()
            if conversation.created
            else "undated"
        )
        lines.append(f"## {date} — {conversation.title or 'Untitled'}")
        lines.append("")
        for message in conversation.messages:
            # Third-level here so a message's own `##` headings cannot be
            # mistaken for the conversation boundaries above.
            label = render.ROLE_LABELS.get(message.role, message.role.title())
            lines.append(f"### {label}")
            lines.append("")
            lines.append(message.text.strip() or "_(empty message)_")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def group_stem(group: Group) -> str:
    """Filename stem for a merged group."""
    start, _ = group.span
    parts = []
    if start:
        parts.append(start.strftime("%Y-%m"))
    slug = render.slugify(group.title)
    if slug:
        parts.append(slug)
    return "-".join(parts) or "merged"


def write_groups(directory: Path, groups: Iterable[Group]) -> list[Path]:
    """Write one Markdown file per group; returns the paths written.

    Idempotent: the directory ends up holding exactly the current grouping.
    Re-running overwrites rather than accumulating, and documents from an
    earlier run whose group no longer exists are removed — this runs daily, so
    appending would pile up a fresh copy of everything every day.
    """
    directory.mkdir(parents=True, exist_ok=True)

    written = []
    used: set[str] = set()
    for group in groups:
        stem = group_stem(group)
        candidate, counter = stem, 2
        # Disambiguate only within this run; across runs the name is stable.
        while candidate in used:
            candidate = f"{stem}-{counter}"
            counter += 1
        used.add(candidate)
        path = directory / f"{candidate}.md"
        path.write_text(render_group(group), encoding="utf-8")
        written.append(path)

    keep = {path.name for path in written}
    for stale in directory.glob("*.md"):
        if stale.name not in keep:
            stale.unlink()
    return written


def summarize(groups: Sequence[Group]) -> str:
    """A human-readable report of what would be merged."""
    multi = [group for group in groups if len(group.conversations) > 1]
    dupes = sum(len(group.duplicates) for group in groups)
    lines = [
        f"{sum(len(g.conversations) for g in groups)} conversation(s) "
        f"in {len(groups)} group(s); {len(multi)} group(s) merge more than one.",
    ]
    if dupes:
        lines.append(f"{dupes} exact duplicate(s) collapsed.")
    for group in groups:
        if len(group.conversations) == 1 and not group.duplicates:
            continue
        lines.append(f"\n  {group.title}  ({len(group.conversations)} conversations)")
        for conversation in group.conversations:
            date = (
                conversation.created.date().isoformat()
                if conversation.created
                else "undated"
            )
            lines.append(f"    - {date}  {conversation.title or conversation.id}")
        for duplicate in group.duplicates:
            date = (
                duplicate.created.date().isoformat() if duplicate.created else "undated"
            )
            lines.append(
                f"    x {date}  {duplicate.title or duplicate.id}  (exact duplicate)"
            )
    return "\n".join(lines)
