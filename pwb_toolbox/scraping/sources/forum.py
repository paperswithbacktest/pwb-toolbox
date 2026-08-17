"""Collect trading scripts posted in forum threads.

Aimed at the thinkorswim community boards -- usethinkscript.com and the like --
where studies are pasted directly into posts, but nothing here is specific to
one site. Posts are located through common container conventions, code through
standard ``<pre>``/``<code>`` elements plus the BBCode wrappers the usual forum
engines emit, and pagination through the standard ``rel="next"`` relation. A
site that does none of those simply yields nothing.

Free and paid live side by side on these boards, so two things get dropped by
default: pages that say their content needs a login or a paid tier, and posts
whose code advertises itself as commercial.

Every candidate is confirmed by :func:`~pwb_toolbox.scraping.languages.classify`
before it becomes a record, which is what keeps quoted prose, shell snippets and
navigation text out of the corpus.
"""

from ..extract import code_candidates, looks_paywalled, next_page_url, page_title
from ..languages import (
    classify,
    declaration,
    is_probably_commercial,
    pine_version,
    thinkscript_kind,
    thinkscript_pane,
)
from ..models import PINESCRIPT, ScriptRecord
from ..polite import PoliteSession


class ForumSource:
    """Walks a forum thread and yields the scripts posted in it."""

    def __init__(
        self,
        session: PoliteSession | None = None,
        skip_commercial: bool = True,
        min_chars: int = 60,
        max_pages: int = 1,
    ):
        self.session = session or PoliteSession(min_interval=2.0)
        self.skip_commercial = skip_commercial
        # Forum posts are full of one-line fragments quoted mid-discussion;
        # a length floor keeps those out without needing a smarter parser.
        self.min_chars = min_chars
        self.max_pages = max_pages
        self.warnings: list[str] = []

    def _record(self, candidate, code, language, url, thread, thread_title):
        kind = None
        version = None
        title = ""
        extra = {"thread": thread}

        if language == PINESCRIPT:
            found = declaration(code)
            if found is not None:
                kind, title = found
            version = pine_version(code)
        else:
            # thinkScript carries no title of its own, so the thread names it.
            kind = thinkscript_kind(code)
            extra["pane"] = thinkscript_pane(code)

        return ScriptRecord(
            source="forum",
            url=url,
            language=language,
            title=title or thread_title or thread,
            code=code,
            author=candidate.author,
            license=None,
            pine_version=version,
            kind=kind,
            extra=extra,
        )

    def collect(self, url: str):
        """Yield a :class:`ScriptRecord` for each script found in the thread."""
        page_url = url
        thread_title = ""
        seen_pages = {page_url}

        for _ in range(max(self.max_pages, 1)):
            resp = self.session.get(page_url)
            if resp.status_code != 200:
                self.warnings.append(f"{page_url}: HTTP {resp.status_code}")
                return

            html = resp.text
            if looks_paywalled(html):
                self.warnings.append(
                    f"{page_url}: page is gated behind a login or paid tier"
                )
                return

            thread_title = thread_title or page_title(html)

            for candidate in code_candidates(html, base_url=page_url):
                code = candidate.text.strip()
                if len(code) < self.min_chars:
                    continue
                language = classify(code)
                if language is None:
                    continue
                if self.skip_commercial and is_probably_commercial(code):
                    self.warnings.append(
                        f"{candidate.anchor or page_url}: skipped (reads as commercial)"
                    )
                    continue
                yield self._record(
                    candidate,
                    code,
                    language,
                    candidate.anchor or page_url,
                    url,
                    thread_title,
                )

            following = next_page_url(html, page_url)
            if following is None or following in seen_pages:
                return
            seen_pages.add(following)
            page_url = following
