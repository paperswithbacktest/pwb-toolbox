"""Collect PineScript and thinkScript from open-source GitHub repositories.

This is the source to reach for by default. It goes through the documented
REST API rather than scraping HTML, it carries each repository's license into
the resulting records, and by default it refuses to keep code that is not
released under a permissive license.
"""

import base64
import os

from ..languages import (
    declaration,
    is_probably_commercial,
    looks_like_pinescript,
    looks_like_thinkscript,
    pine_version,
)
from ..models import PINESCRIPT, THINKSCRIPT, ScriptRecord
from ..polite import PoliteSession

API_ROOT = "https://api.github.com"

#: Licenses under which collected code may be reused with attribution alone.
PERMISSIVE_LICENSES = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "CC0-1.0",
        "MPL-2.0",
    }
)

#: Extensions worth opening, mapped to the languages they might contain.
CANDIDATE_EXTENSIONS = {
    ".pine": (PINESCRIPT,),
    ".pinescript": (PINESCRIPT,),
    ".ts": (THINKSCRIPT,),
    ".tos": (THINKSCRIPT,),
    ".thinkscript": (THINKSCRIPT,),
    ".txt": (PINESCRIPT, THINKSCRIPT),
}

_DETECTORS = {
    PINESCRIPT: looks_like_pinescript,
    THINKSCRIPT: looks_like_thinkscript,
}


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


class SkippedRepository(RuntimeError):
    """Raised when a repository is rejected before any file is read."""


def _extension(path: str) -> str:
    _, dot, ext = path.rpartition(".")
    return f".{ext.lower()}" if dot else ""


def detect_language(path: str, code: str) -> str | None:
    """Return the language of ``code``, or ``None`` if it is neither.

    The extension only decides which detectors are worth running; the content
    always has the final say.
    """
    for language in CANDIDATE_EXTENSIONS.get(_extension(path), ()):
        if _DETECTORS[language](code):
            return language
    return None


class GitHubSource:
    """Walks a repository tree and yields the trading scripts it contains."""

    def __init__(
        self,
        session: PoliteSession | None = None,
        token: str | None = None,
        allowed_licenses=PERMISSIVE_LICENSES,
        require_license: bool = True,
        skip_commercial: bool = True,
        max_bytes: int = 200_000,
    ):
        # The API tolerates a brisk pace; the shared default of one second is
        # aimed at HTML scraping and would make large repositories crawl.
        self.session = session or PoliteSession(min_interval=0.25)
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.allowed_licenses = frozenset(allowed_licenses)
        self.require_license = require_license
        self.skip_commercial = skip_commercial
        self.max_bytes = max_bytes
        self.warnings: list[str] = []

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _api(self, path: str, **params) -> dict:
        resp = self.session.get(
            f"{API_ROOT}{path}", headers=self._headers(), params=params or None
        )
        if resp.status_code != 200:
            raise GitHubError(f"GET {path} returned HTTP {resp.status_code}")
        return resp.json()

    def repository(self, repo: str) -> dict:
        """Metadata for ``owner/name``."""
        return self._api(f"/repos/{repo}")

    def _license_of(self, meta: dict) -> str | None:
        spdx = (meta.get("license") or {}).get("spdx_id")
        return None if spdx in (None, "NOASSERTION", "") else spdx

    def _tree(self, repo: str, ref: str) -> list[dict]:
        payload = self._api(f"/repos/{repo}/git/trees/{ref}", recursive="1")
        if payload.get("truncated"):
            self.warnings.append(
                f"{repo}: tree listing was truncated by the API; "
                "some files were not examined"
            )
        return [item for item in payload.get("tree", []) if item.get("type") == "blob"]

    def _blob(self, repo: str, sha: str) -> str | None:
        payload = self._api(f"/repos/{repo}/git/blobs/{sha}")
        if payload.get("encoding") != "base64":
            return None
        try:
            return base64.b64decode(payload["content"]).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return None

    def collect(self, repo: str, ref: str | None = None):
        """Yield a :class:`ScriptRecord` for every script found in ``repo``.

        Raises :class:`SkippedRepository` when the repository's license does
        not permit reuse and ``require_license`` is set.
        """
        meta = self.repository(repo)
        license_id = self._license_of(meta)
        if self.require_license and license_id not in self.allowed_licenses:
            raise SkippedRepository(
                f"{repo}: license {license_id or 'unspecified'} is not in the "
                "allowed set; pass require_license=False to collect anyway"
            )

        ref = ref or meta.get("default_branch") or "HEAD"
        owner = repo.split("/")[0]

        for item in self._tree(repo, ref):
            path = item["path"]
            if _extension(path) not in CANDIDATE_EXTENSIONS:
                continue
            if item.get("size", 0) > self.max_bytes:
                continue

            code = self._blob(repo, item["sha"])
            if not code:
                continue
            language = detect_language(path, code)
            if language is None:
                continue
            if self.skip_commercial and is_probably_commercial(code):
                # A permissive repository license does not override a header
                # comment saying the file itself is paid or non-redistributable.
                self.warnings.append(f"{repo}: skipped {path} (reads as commercial)")
                continue

            kind, title = (None, "")
            if language == PINESCRIPT:
                found = declaration(code)
                if found is not None:
                    kind, title = found

            yield ScriptRecord(
                source="github",
                url=f"https://github.com/{repo}/blob/{ref}/{path}",
                language=language,
                title=title or path.rsplit("/", 1)[-1],
                code=code,
                author=owner,
                license=license_id,
                pine_version=pine_version(code) if language == PINESCRIPT else None,
                kind=kind,
                extra={"repo": repo, "path": path, "ref": ref},
            )
