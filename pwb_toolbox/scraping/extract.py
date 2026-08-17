"""Shared helpers for pulling code out of a rendered HTML page.

Every collector faces the same problem: the markup of a site that cannot be
reached from CI is a guess, and an extractor keyed on one CSS class is a single
redesign away from quietly returning navigation chrome.

So none of these functions decide what is code. They gather candidates cheaply
and broadly -- from standard elements first, from common forum containers
second -- and leave the verdict to a language predicate in
:mod:`pwb_toolbox.scraping.languages`. A wrong guess then yields nothing, which
is a bug you notice, instead of garbage, which is a bug you ship.
"""

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

#: Elements that hold preformatted code. The first two are standard HTML; the
#: rest are conventions shared by the common forum engines.
CODE_SELECTORS = (
    "pre",
    "code",
    ".bbCodeBlock",
    ".bbCodeCode",
    ".codeBlock",
    ".code",
)

#: Containers that usually wrap a single forum post.
POST_SELECTORS = ("article", ".message", "li.post", "div.post")

#: Phrases that mean the page is withholding its content behind a login or a
#: paid tier. Collectors treat a match as "nothing to see", not as an error.
PAYWALL_MARKERS = (
    "you must be a member",
    "members only",
    "member only",
    "log in to view",
    "login to view",
    "register to view",
    "sign up to view",
    "upgrade to view",
    "subscribe to view",
    "vip members",
    "this content is for",
    "paid members",
)


@dataclass(frozen=True)
class CodeCandidate:
    """A block of text that might be code, plus where on the page it came from."""

    text: str
    author: str | None = None
    anchor: str | None = None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def looks_paywalled(html: str) -> bool:
    """True when the page says its content is behind a login or paid tier.

    Code blocks are removed before matching. A study whose header comment reads
    "paid members only" is a commercial *script* on an ordinary page, which is
    :func:`~pwb_toolbox.scraping.languages.is_probably_commercial`'s call to
    make -- conflating the two would report the wrong diagnosis for an empty
    corpus.
    """
    soup = _soup(html)
    for node in soup.select(", ".join(CODE_SELECTORS)):
        node.decompose()
    text = soup.get_text(" ", strip=True).lower()
    return any(marker in text for marker in PAYWALL_MARKERS)


def json_string_values(html: str, keys):
    """Yield decoded values of any JSON string keyed by one of ``keys``.

    Single-page apps hand the code to the browser as JSON inside a ``<script>``
    tag rather than as markup, so this covers what element scraping misses.
    """
    pattern = re.compile(
        r'"(?:%s)"\s*:\s*"((?:[^"\\]|\\.)*)"' % "|".join(re.escape(k) for k in keys)
    )
    soup = _soup(html)
    blobs = [tag.string or "" for tag in soup.find_all("script")]
    blobs.append(html)

    for blob in blobs:
        if not blob:
            continue
        for raw in pattern.findall(blob):
            try:
                yield json.loads(f'"{raw}"')
            except json.JSONDecodeError:
                continue


def _author_of(post) -> str | None:
    author = post.get("data-author") if hasattr(post, "get") else None
    if author:
        return author.strip()
    for selector in (".message-name", ".username", ".author", ".postUsername"):
        found = post.select_one(selector)
        if found is not None:
            name = found.get_text(" ", strip=True)
            if name:
                return name
    return None


def _anchor_of(post, base_url: str | None) -> str | None:
    link = post.select_one('a[href*="#post"], a[href*="#p"]')
    if link is not None and link.get("href"):
        href = link["href"]
        return urljoin(base_url, href) if base_url else href
    post_id = post.get("id") if hasattr(post, "get") else None
    if post_id and base_url:
        return f"{base_url}#{post_id}"
    return f"#{post_id}" if post_id else None


def code_candidates(html: str, base_url: str | None = None) -> list[CodeCandidate]:
    """Every plausible code block on the page, with its post attribution.

    Blocks are deduplicated by their text, because a ``<pre><code>`` pair
    matches twice and would otherwise be collected twice.
    """
    soup = _soup(html)
    posts = soup.select(", ".join(POST_SELECTORS))
    scopes = [(post, _author_of(post), _anchor_of(post, base_url)) for post in posts]
    if not scopes:
        scopes = [(soup, None, None)]

    seen: set[str] = set()
    found: list[CodeCandidate] = []
    for scope, author, anchor in scopes:
        for node in scope.select(", ".join(CODE_SELECTORS)):
            text = node.get_text("\n")
            key = " ".join(text.split())
            if not key or key in seen:
                continue
            seen.add(key)
            found.append(CodeCandidate(text=text, author=author, anchor=anchor))
    return found


def page_title(html: str) -> str:
    """The page's ``<h1>``, falling back to ``<title>``."""
    soup = _soup(html)
    heading = soup.find("h1")
    if heading is not None:
        title = heading.get_text(" ", strip=True)
        if title:
            return title
    if soup.title is not None:
        return soup.title.get_text(" ", strip=True)
    return ""


def next_page_url(html: str, base_url: str) -> str | None:
    """The thread's next page, via ``rel="next"``.

    Deliberately limited to the standard relation rather than any particular
    forum's pager markup, so it either works by spec or reports nothing.
    """
    soup = _soup(html)
    link = soup.find("a", rel="next") or soup.find("link", rel="next")
    if link is not None and link.get("href"):
        return urljoin(base_url, link["href"])
    return None
