"""HTTP client for grok.com's internal chat endpoints.

These endpoints are not a published API. Paths move between builds, so every
call tries a list of candidates and remembers the one that answered; all of them
are overridable from the CLI. Responses are handed back as raw decoded JSON —
interpretation is :mod:`schema`'s job, and the raw form is what gets archived.
"""

from __future__ import annotations

import time
from typing import Any, Iterator, Sequence

import requests

from . import schema

BASE_URL = "https://grok.com"

# Ordered by how likely each is to be the live path; the first non-404 wins.
LIST_PATHS: tuple[str, ...] = (
    "/rest/app-chat/conversations",
    "/rest/app-chat/conversations/list",
    "/api/rest/app-chat/conversations",
)
DETAIL_PATHS: tuple[str, ...] = (
    "/rest/app-chat/conversations/{id}/response-node",
    "/rest/app-chat/conversations/{id}/responses",
    "/rest/app-chat/conversations/{id}",
)

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_PAGES = 1000


class GrokError(RuntimeError):
    """A request to grok.com failed in a way the caller cannot retry past."""


class SessionExpired(GrokError):
    """The cookie was rejected; the browser session needs re-copying."""


class EndpointNotFound(GrokError):
    """None of the candidate paths answered."""


class GrokClient:
    """Minimal, polite client for the grok.com chat endpoints."""

    def __init__(
        self,
        cookie: str,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        delay: float = 0.5,
        timeout: float = 30.0,
        max_retries: int = 4,
        list_paths: Sequence[str] = LIST_PATHS,
        detail_paths: Sequence[str] = DETAIL_PATHS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.list_paths = tuple(list_paths)
        self.detail_paths = tuple(detail_paths)
        self._resolved: dict[str, str] = {}
        self._last_request = 0.0

        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "cookie": cookie,
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9",
                "user-agent": _BROWSER_UA,
                "referer": f"{self.base_url}/",
                "origin": self.base_url,
            }
        )

    # -- transport ---------------------------------------------------------

    def _throttle(self) -> None:
        if not self.delay:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Issue one request, retrying transient failures with backoff."""
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
            except requests.RequestException as error:
                last_error = error
                if attempt == self.max_retries:
                    break
                time.sleep(2**attempt)
                continue
            finally:
                self._last_request = time.monotonic()

            if response.status_code in (401, 403):
                raise SessionExpired(
                    f"grok.com rejected the session cookie ({response.status_code}). "
                    "Copy a fresh one from a signed-in browser and retry."
                )
            if response.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                time.sleep(self._retry_after(response, attempt))
                continue
            return response

        raise GrokError(f"{method} {path} failed after retries: {last_error}")

    @staticmethod
    def _retry_after(response: requests.Response, attempt: int) -> float:
        """Seconds to wait, honouring Retry-After when the server sends one."""
        header = response.headers.get("retry-after", "")
        try:
            return min(60.0, max(0.0, float(header)))
        except (TypeError, ValueError):
            return float(2**attempt)

    @staticmethod
    def _json(response: requests.Response, path: str) -> Any:
        """Decode a JSON body, turning a login-page redirect into a clear error."""
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            snippet = response.text[:200].replace("\n", " ")
            if "<html" in snippet.lower():
                raise SessionExpired(
                    f"{path} returned an HTML page instead of JSON, which usually "
                    "means the session cookie has expired."
                )
            raise GrokError(
                f"{path} returned {content_type or 'no content-type'}: {snippet}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise GrokError(f"{path} returned invalid JSON: {error}") from error

    def _call(
        self, kind: str, candidates: Sequence[str], fmt: dict[str, str], **kwargs: Any
    ) -> Any:
        """Call the first candidate path that is not a 404, caching the winner."""
        cached = self._resolved.get(kind)
        templates = [cached] if cached else list(candidates)

        tried: list[str] = []
        for template in templates:
            path = template.format(**fmt)
            response = self._request("GET", path, **kwargs)
            if response.status_code == 404:
                tried.append(path)
                continue
            if response.status_code >= 400:
                raise GrokError(f"GET {path} failed with {response.status_code}.")
            self._resolved[kind] = template
            return self._json(response, path)

        raise EndpointNotFound(
            f"No {kind} endpoint answered. Tried: {', '.join(tried)}. "
            "grok.com may have moved it; pass --list-path/--detail-path to override."
        )

    # -- API ---------------------------------------------------------------

    def list_page(self, page_size: int = 100, cursor: str | None = None) -> Any:
        """Fetch one page of the conversation listing."""
        params: dict[str, Any] = {"pageSize": page_size}
        if cursor:
            params["cursor"] = cursor
        return self._call("list", self.list_paths, {}, params=params)

    def list_conversations(
        self, page_size: int = 100, limit: int | None = None
    ) -> Iterator[dict]:
        """Yield every conversation entry, walking pagination to exhaustion."""
        cursor: str | None = None
        seen: set[str] = set()
        yielded = 0

        for _ in range(_MAX_PAGES):
            page = self.list_page(page_size=page_size, cursor=cursor)
            fresh = 0
            for entry in schema.iter_conversation_payloads(page):
                key = str(schema.pick(entry, schema.ID_KEYS, "") or "")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                fresh += 1
                yielded += 1
                yield entry
                if limit is not None and yielded >= limit:
                    return

            # No new ids means the cursor stopped advancing: stop rather than
            # loop forever against an offset-style endpoint that ignores it.
            if fresh == 0:
                return
            cursor = schema.next_cursor(page)
            if not cursor:
                return

    def fetch_detail(self, conversation_id: str) -> Any:
        """Fetch the turns of one conversation."""
        return self._call("detail", self.detail_paths, {"id": conversation_id})
