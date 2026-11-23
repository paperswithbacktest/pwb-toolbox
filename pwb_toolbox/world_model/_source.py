"""Where the World Model tables are read from: the Hub, or a local directory.

The tables are Parquet, sharded by the year of ``known_at`` (``train-2013.parquet``).
A read never needs a shard whose year is after the knowledge cutoff, so those
are neither downloaded nor opened. Rows are filtered inside the Parquet scan
(``pyarrow.dataset``), so asking for a few tickers does not materialise the
whole table.
"""

from __future__ import annotations

import os
import re

import pyarrow as pa
import pyarrow.dataset as ds

ORGANISATION = "paperswithbacktest"
ENTITIES = "WorldModel-Entities"
IDENTIFIERS = "WorldModel-Identifiers"
EDGES_PREFIX = "WorldModel-Edges-"
#: A directory holding one sub-directory per table (``WorldModel-Identifiers/``...).
LOCAL_DIR_ENV = "PWB_WORLD_MODEL_DIR"

_SHARD_YEAR = re.compile(r"(?:^|/)[^/]*?(\d{4})\.parquet$")


class WorldModelNotAvailable(LookupError):
    """A World Model table is not published, not reachable, or not readable with this token."""


def shard_year(path: str):
    """Year in a shard's file name (``train-2013.parquet`` -> 2013), or ``None``."""
    found = _SHARD_YEAR.search(path.replace(os.sep, "/"))
    return int(found.group(1)) if found else None


def in_window(paths: list[str], max_year) -> list[str]:
    """The shards that can hold rows with ``known_at`` up to ``max_year``."""
    if max_year is None:
        return list(paths)
    return [p for p in paths if (shard_year(p) is None or shard_year(p) <= max_year)]


def scan(paths: list[str], columns=None, filter=None) -> pa.Table | None:
    """Filtered read of Parquet files; ``None`` when there is no file."""
    if not paths:
        return None
    dataset = ds.dataset(sorted(paths), format="parquet")
    if columns is not None:
        columns = [c for c in columns if c in dataset.schema.names]
    return dataset.to_table(columns=columns, filter=filter)


class LocalSource:
    """Tables read from a directory: ``<root>/<Table>/**.parquet``.

    ``<root>/<Table>`` may also hold several generations, one sub-directory each
    with its own ``manifest.json`` (what the build job writes); the newest by
    name is read. ``tables`` maps a table name to a directory directly.
    """

    def __init__(self, root: str | None = None, tables: dict | None = None):
        self.root = os.path.expanduser(root) if root else None
        self.tables = {k: os.path.expanduser(v) for k, v in (tables or {}).items()}

    def describe(self) -> str:
        return f"local directory {self.root}" if self.root else "local directories"

    def _directory(self, table: str) -> str:
        if table in self.tables:
            return self.tables[table]
        if self.root is None:
            raise WorldModelNotAvailable(f"{table}: no local directory given for it")
        directory = os.path.join(self.root, table)
        if not os.path.isdir(directory):
            raise WorldModelNotAvailable(f"{table}: not found in {self.root}")
        if os.path.exists(os.path.join(directory, "manifest.json")):
            return directory
        generations = sorted(
            d for d in os.listdir(directory)
            if os.path.exists(os.path.join(directory, d, "manifest.json"))
        )
        return os.path.join(directory, generations[-1]) if generations else directory

    def files(self, table: str, max_year=None) -> list[str]:
        directory = self._directory(table)
        paths = []
        for dirpath, _dirs, names in os.walk(directory):
            paths.extend(os.path.join(dirpath, n) for n in names if n.endswith(".parquet"))
        if not paths:
            raise WorldModelNotAvailable(f"{table}: no Parquet file under {directory}")
        return in_window(sorted(paths), max_year)

    def edge_families(self) -> list[str]:
        roots = [self.root] if self.root else []
        names = {t for t in self.tables if t.startswith(EDGES_PREFIX)}
        for root in roots:
            if os.path.isdir(root):
                names.update(d for d in os.listdir(root) if d.startswith(EDGES_PREFIX))
        return sorted(names)


class HubSource:
    """Tables read from the Hugging Face Hub (private datasets: a token is needed).

    ``revision`` pins every table to one commit (``str``), or each table to its
    own (``{"WorldModel-Identifiers": "<sha>", ...}``); unpinned tables are
    read at their current revision, which the prepared-data cache records.
    """

    def __init__(self, revision=None, token=None):
        self.revision = revision
        self.token = token if token is not None else (os.getenv("HF_ACCESS_TOKEN") or None)
        self._snapshots: dict = {}

    def describe(self) -> str:
        return "the Hugging Face Hub"

    def _revision_of(self, table: str):
        if isinstance(self.revision, dict):
            return self.revision.get(table)
        return self.revision

    def snapshot(self, table: str) -> tuple[str, list[str]]:
        """``(commit sha, Parquet shards)`` of a table."""
        if table in self._snapshots:
            return self._snapshots[table]
        from ..datasets import _hub_snapshot, _list_hf_split_parquet_files
        from ..datasets import prepared_cache as _prepared

        repo_id = f"{ORGANISATION}/{table}"
        revision = self._revision_of(table)
        try:
            if revision is None:
                sha, files = _hub_snapshot(repo_id, self.token)
            else:
                from huggingface_hub import HfApi

                info = HfApi(token=self.token).dataset_info(repo_id, revision=revision)
                sha, files = info.sha, sorted(s.rfilename for s in info.siblings)
                _prepared.note_revision("hub", repo_id, sha)
        except Exception as exc:  # noqa: BLE001 - one message for every cause
            raise WorldModelNotAvailable(
                f"{repo_id} could not be read ({type(exc).__name__}). It is a private "
                "dataset: check that it is published and that HF_ACCESS_TOKEN can read it, "
                f"or read a local build with local_dir= / {LOCAL_DIR_ENV}."
            ) from exc
        shards = _list_hf_split_parquet_files(files, "train")
        if not shards:
            raise WorldModelNotAvailable(f"{repo_id}@{sha[:8]} holds no train shard")
        self._snapshots[table] = (sha, shards)
        return self._snapshots[table]

    def files(self, table: str, max_year=None) -> list[str]:
        from huggingface_hub import hf_hub_download

        sha, shards = self.snapshot(table)
        return [
            hf_hub_download(
                repo_id=f"{ORGANISATION}/{table}", repo_type="dataset",
                filename=name, revision=sha, token=self.token,
            )
            for name in in_window(shards, max_year)
        ]

    def edge_families(self) -> list[str]:
        if isinstance(self.revision, dict):
            pinned = sorted(t for t in self.revision if t.startswith(EDGES_PREFIX))
            if pinned:
                return pinned
        from huggingface_hub import HfApi

        try:
            found = HfApi(token=self.token).list_datasets(author=ORGANISATION, search=EDGES_PREFIX)
            names = sorted(d.id.split("/", 1)[1] for d in found)
        except Exception as exc:  # noqa: BLE001
            raise WorldModelNotAvailable(
                f"the {EDGES_PREFIX}<Family> datasets could not be listed on the Hub "
                f"({type(exc).__name__}); pass families=[...] explicitly"
            ) from exc
        return [n for n in names if n.startswith(EDGES_PREFIX)]
