"""On-disk corpus of scraped scripts.

Layout under ``root``::

    manifest.jsonl          one JSON object per script, including its hash
    scripts/ab/abcd....pine the script body, sharded by hash prefix

Records are keyed by the SHA-256 of their code, so the same script collected
twice -- from two repositories, or on a later run -- is stored once.
"""

import json
from pathlib import Path

from .models import ScriptRecord

MANIFEST_NAME = "manifest.jsonl"


class ScriptStore:
    """Append-only, deduplicating store for :class:`ScriptRecord` objects."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.manifest_path = self.root / MANIFEST_NAME
        self._hashes = {entry["content_hash"] for entry in self.entries()}

    def entries(self) -> list[dict]:
        """Manifest rows, oldest first. Empty when the store is new."""
        if not self.manifest_path.exists():
            return []
        rows = []
        with self.manifest_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def records(self) -> list[ScriptRecord]:
        """Rehydrate every stored record, reading code back from disk."""
        out = []
        for entry in self.entries():
            code = (self.root / entry["path"]).read_text(encoding="utf-8")
            payload = dict(entry, code=code)
            out.append(ScriptRecord.from_dict(payload))
        return out

    def __len__(self) -> int:
        return len(self._hashes)

    def __contains__(self, record: ScriptRecord) -> bool:
        return record.content_hash in self._hashes

    def add(self, record: ScriptRecord) -> bool:
        """Store ``record``. Returns ``False`` when it was already present."""
        digest = record.content_hash
        if digest in self._hashes:
            return False

        relative = Path("scripts") / digest[:2] / f"{digest}{record.extension}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record.code, encoding="utf-8")

        entry = record.to_dict()
        # The body lives in its own file; the manifest carries the pointer.
        entry.pop("code")
        entry["content_hash"] = digest
        entry["path"] = relative.as_posix()

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._hashes.add(digest)
        return True

    def extend(self, records) -> int:
        """Add many records, returning how many were new."""
        return sum(1 for record in records if self.add(record))
