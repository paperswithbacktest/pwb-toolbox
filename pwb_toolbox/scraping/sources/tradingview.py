"""Collect open-source scripts from TradingView script pages.

Read this before using it
-------------------------

TradingView licenses the content on its site for display, and its terms
restrict automated non-display use. Authors of published scripts also retain
their rights in the code. Fetching a handful of open-source scripts you intend
to study is a different act from building a bulk corpus, and only the former is
a defensible reading of those terms -- so this source is opt-in, one URL at a
time, with no crawler that discovers new pages on its own.

Extracting the source of a protected or invite-only script is out of scope
here and is a straightforward IP violation; this module only reads what the
page already renders for open-source publications.

The page-layout caveat
----------------------

:func:`extract_pine_source` is covered by tests, but only against synthetic
fixtures -- TradingView is unreachable from the environment this module was
written in, so the live page structure has not been confirmed. The extractor
therefore validates whatever it finds with
:func:`~pwb_toolbox.scraping.languages.looks_like_pinescript` and returns
``None`` rather than returning something that merely came out of the right
element. If TradingView changes its markup you will get nothing, not garbage.
"""

import json
import re

from bs4 import BeautifulSoup

from ..languages import declaration, looks_like_pinescript, pine_version
from ..models import PINESCRIPT, ScriptRecord
from ..polite import PoliteSession

SCRIPT_URL_RE = re.compile(r"^https?://[\w.-]*tradingview\.com/script/[\w-]+/?")

_SOURCE_KEYS = ("source", "script_source", "sourceCode")
_JSON_STRING_RE = re.compile(r'"(?:%s)"\s*:\s*"((?:[^"\\]|\\.)*)"')


class TermsNotAccepted(RuntimeError):
    """Raised when the source is used without acknowledging the terms."""


def _candidate_strings(html: str):
    """Yield decoded values of any JSON ``source``-like key found in the page."""
    soup = BeautifulSoup(html, "html.parser")
    blobs = [tag.string or "" for tag in soup.find_all("script")]
    blobs.append(html)

    pattern = re.compile(_JSON_STRING_RE.pattern % "|".join(_SOURCE_KEYS))
    for blob in blobs:
        if not blob:
            continue
        for raw in pattern.findall(blob):
            try:
                yield json.loads(f'"{raw}"')
            except json.JSONDecodeError:
                continue


def extract_pine_source(html: str) -> str | None:
    """Pull PineScript out of a rendered script page.

    Returns ``None`` unless the recovered text actually reads as PineScript.
    """
    for candidate in _candidate_strings(html):
        if looks_like_pinescript(candidate):
            return candidate

    # Some pages render the code as plain text rather than embedding it.
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["pre", "code"]):
        text = tag.get_text("\n")
        if looks_like_pinescript(text):
            return text
    return None


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if heading is not None:
        return heading.get_text(" ", strip=True)
    if soup.title is not None:
        return soup.title.get_text(" ", strip=True)
    return ""


class TradingViewSource:
    """Fetches one published script page at a time.

    ``accept_terms`` must be set explicitly; the default refuses to run so that
    nobody points this at the site without having read the note above.
    """

    def __init__(
        self,
        session: PoliteSession | None = None,
        accept_terms: bool = False,
    ):
        self.session = session or PoliteSession(min_interval=5.0)
        self.accept_terms = accept_terms

    def fetch(self, url: str) -> ScriptRecord | None:
        """Return the script published at ``url``, or ``None`` if none is public.

        Raises :class:`TermsNotAccepted` unless ``accept_terms`` was set, and
        :class:`~pwb_toolbox.scraping.polite.RobotsDisallowed` when the site's
        ``robots.txt`` forbids the path.
        """
        if not self.accept_terms:
            raise TermsNotAccepted(
                "TradingViewSource(accept_terms=True) is required. See the "
                "module docstring for what you are agreeing to."
            )
        if not SCRIPT_URL_RE.match(url):
            raise ValueError(f"not a TradingView script URL: {url}")

        resp = self.session.get(url)
        if resp.status_code != 200:
            return None

        code = extract_pine_source(resp.text)
        if code is None:
            return None

        kind, title = (None, "")
        found = declaration(code)
        if found is not None:
            kind, title = found

        return ScriptRecord(
            source="tradingview",
            url=url,
            language=PINESCRIPT,
            title=title or extract_title(resp.text),
            code=code,
            license=None,
            pine_version=pine_version(code),
            kind=kind,
        )
