"""Loading grok.com session credentials without ever printing them.

There is no public OAuth flow for the grok.com web app, so the exporter reuses
the cookies from a logged-in browser session. The friendliest way to hand those
over is DevTools' "Copy as cURL": save it to a file and let this module pull the
cookie header out, rather than asking anyone to hand-edit a cookie string.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

# Cookies grok.com sets for a signed-in session. Absent any of these the export
# will come back empty or 401, so warn early rather than after a long crawl.
EXPECTED_COOKIES = ("sso", "sso-rw")

ENV_VAR = "GROK_COOKIE"

_CURL_COOKIE_RE = re.compile(
    r"""-H\s+(['"])\s*cookie\s*:\s*(?P<value>.*?)\1""",
    re.IGNORECASE | re.DOTALL,
)
_CURL_B_RE = re.compile(r"""(?:^|\s)-b\s+(['"])(?P<value>.*?)\1""", re.DOTALL)


class AuthError(RuntimeError):
    """Raised when no usable session cookie can be found."""


def parse_cookie_header(text: str) -> str:
    """Extract a cookie string from raw text, a cookie header, or a cURL command.

    Accepts the whole "Copy as cURL" blob, a bare ``cookie: a=1; b=2`` header
    line, or just ``a=1; b=2``.
    """
    text = (text or "").strip()
    if not text:
        return ""

    for pattern in (_CURL_COOKIE_RE, _CURL_B_RE):
        match = pattern.search(text)
        if match:
            return _clean(match.group("value"))

    # A multi-line paste where only one line is the cookie header.
    for line in text.splitlines():
        stripped = line.strip().lstrip("-H").strip().strip("'\"").strip()
        if stripped.lower().startswith("cookie:"):
            return _clean(stripped.split(":", 1)[1])

    if "=" in text and "\n" not in text.strip():
        return _clean(text)

    # Last resort: a cURL command whose quoting shlex can untangle.
    try:
        tokens = shlex.split(text)
    except ValueError:
        return ""
    for index, token in enumerate(tokens):
        if token in ("-H", "--header") and index + 1 < len(tokens):
            header = tokens[index + 1]
            if header.lower().startswith("cookie:"):
                return _clean(header.split(":", 1)[1])
        if token in ("-b", "--cookie") and index + 1 < len(tokens):
            return _clean(tokens[index + 1])
    return ""


def _clean(value: str) -> str:
    """Collapse a cookie header onto one line and strip stray quoting."""
    collapsed = " ".join(value.split())
    return collapsed.strip().strip("'\"").strip()


def cookie_names(cookie: str) -> list[str]:
    """Names present in a cookie string. Never returns any value."""
    names = []
    for part in cookie.split(";"):
        name, _, _ = part.strip().partition("=")
        if name:
            names.append(name)
    return names


def missing_cookies(cookie: str) -> list[str]:
    """Expected session cookies absent from ``cookie``."""
    present = set(cookie_names(cookie))
    return [name for name in EXPECTED_COOKIES if name not in present]


def load_cookie(source: str | os.PathLike[str] | None = None) -> str:
    """Resolve the session cookie from a file, a literal string, or the env.

    Precedence: explicit ``source`` (a path if it exists, else the literal
    value), then ``$GROK_COOKIE``.
    """
    if source:
        path = Path(source)
        # Guard against a long cookie string tripping the filesystem's name limit.
        try:
            is_file = path.is_file()
        except (OSError, ValueError):
            is_file = False
        raw = path.read_text(encoding="utf-8") if is_file else str(source)
        cookie = parse_cookie_header(raw)
        if cookie:
            return cookie
        origin = f"file {path}" if is_file else "the --cookie value"
        raise AuthError(f"No cookie header found in {origin}.")

    from_env = parse_cookie_header(os.environ.get(ENV_VAR, ""))
    if from_env:
        return from_env

    raise AuthError(
        "No Grok session cookie provided. Open grok.com while signed in, open "
        "DevTools > Network, right-click any request to grok.com and choose "
        '"Copy as cURL", save it to a file, then pass --cookie <file> (or set '
        f"${ENV_VAR})."
    )
