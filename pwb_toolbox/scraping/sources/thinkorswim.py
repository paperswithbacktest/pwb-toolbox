"""Collect thinkScript studies from thinkorswim ``tos.mx`` share links.

``tos.mx`` is thinkorswim's own sharing mechanism: an author exports a study,
strategy or chart setup and gets back a short link intended to be handed to
other people. Unlike a TradingView script page -- which is site content wrapped
in display-only terms -- a share link exists precisely to be opened by someone
else, so this collector does not gate itself behind a terms flag. It still
honours ``robots.txt``, still fetches one link at a time, and still discovers
nothing on its own.

What it will not give you is the paid tier. Vendors who sell thinkorswim
studies generally do not hand out a readable share link; they add the study to
your account. Anything that does arrive carrying a "paid members only" header
is dropped by the commercial filter unless you ask for it.

The page-layout caveat from ``tradingview.py`` applies here too: ``tos.mx`` is
unreachable from the environment this was written in, so extraction is
validated by content rather than by a confirmed selector. A markup change
yields nothing rather than garbage.
"""

import re

from ..extract import code_candidates, json_string_values, looks_paywalled, page_title
from ..languages import (
    is_probably_commercial,
    looks_like_thinkscript,
    thinkscript_kind,
    thinkscript_pane,
)
from ..models import THINKSCRIPT, ScriptRecord
from ..polite import PoliteSession

#: Share links look like ``http://tos.mx/aBcDeFg``; some carry a ``!`` prefix.
SHARE_URL_RE = re.compile(r"^https?://(?:www\.)?tos\.mx/(!?)([\w-]+)/?$", re.I)

#: JSON keys the page might hand the study source under.
SOURCE_KEYS = ("source", "script", "study", "code", "thinkScript")


def share_id(url: str) -> str | None:
    """The identifier part of a ``tos.mx`` link, or ``None`` if not one."""
    match = SHARE_URL_RE.match(url.strip())
    return match.group(2) if match else None


def extract_thinkscript(html: str) -> str | None:
    """Pull thinkScript out of a rendered share page.

    Returns ``None`` unless the recovered text actually reads as thinkScript,
    so a stale selector fails visibly instead of storing page furniture.
    """
    for candidate in json_string_values(html, SOURCE_KEYS):
        if looks_like_thinkscript(candidate):
            return candidate
    for candidate in code_candidates(html):
        if looks_like_thinkscript(candidate.text):
            return candidate.text
    return None


class ThinkorswimSource:
    """Fetches one ``tos.mx`` share link at a time."""

    def __init__(
        self,
        session: PoliteSession | None = None,
        skip_commercial: bool = True,
    ):
        self.session = session or PoliteSession(min_interval=2.0)
        self.skip_commercial = skip_commercial
        self.warnings: list[str] = []

    def fetch(self, url: str) -> ScriptRecord | None:
        """Return the study behind ``url``, or ``None`` when none is readable."""
        identifier = share_id(url)
        if identifier is None:
            raise ValueError(f"not a tos.mx share URL: {url}")

        resp = self.session.get(url)
        if resp.status_code != 200:
            self.warnings.append(f"{url}: HTTP {resp.status_code}")
            return None

        if looks_paywalled(resp.text):
            self.warnings.append(f"{url}: page is gated behind a login or paid tier")
            return None

        code = extract_thinkscript(resp.text)
        if code is None:
            self.warnings.append(f"{url}: no readable thinkScript on the page")
            return None

        if self.skip_commercial and is_probably_commercial(code):
            self.warnings.append(f"{url}: skipped (reads as commercial)")
            return None

        return ScriptRecord(
            source="thinkorswim",
            url=url,
            language=THINKSCRIPT,
            title=page_title(resp.text) or identifier,
            code=code,
            license=None,
            kind=thinkscript_kind(code),
            extra={"share_id": identifier, "pane": thinkscript_pane(code)},
        )
