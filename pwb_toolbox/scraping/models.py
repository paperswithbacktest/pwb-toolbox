"""Record types for scraped trading-script source code."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib

PINESCRIPT = "pinescript"
THINKSCRIPT = "thinkscript"

#: File extension used when a record is written to disk, keyed by language.
EXTENSIONS = {PINESCRIPT: ".pine", THINKSCRIPT: ".ts"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ScriptRecord:
    """A single trading script together with its provenance.

    ``license`` holds an SPDX identifier when the source reports one. It is
    ``None`` when the upstream repository or page declares no license, which
    means the code is all-rights-reserved rather than freely reusable.
    """

    source: str
    url: str
    language: str
    title: str
    code: str
    author: str | None = None
    license: str | None = None
    pine_version: int | None = None
    kind: str | None = None
    retrieved_at: str = field(default_factory=_utcnow)
    extra: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """SHA-256 of the code, used to deduplicate across sources."""
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()

    @property
    def extension(self) -> str:
        return EXTENSIONS.get(self.language, ".txt")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ScriptRecord":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in payload.items() if k in known})
