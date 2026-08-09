"""Collect PineScript and thinkScript source code from the web.

PineScript is TradingView's language and thinkScript is thinkorswim's; they
are unrelated dialects and are detected, parsed and stored separately here.

The intended entry point is :class:`~pwb_toolbox.scraping.sources.github.GitHubSource`,
which reads open-source repositories through the GitHub API and keeps each
repository's license attached to the code it yields.
"""

from .extract import CodeCandidate, code_candidates, looks_paywalled, next_page_url
from .languages import (
    classify,
    declaration,
    input_names,
    is_probably_commercial,
    looks_like_pinescript,
    looks_like_thinkscript,
    pine_version,
    strip_comments,
    thinkscript_kind,
    thinkscript_pane,
)
from .models import EXTENSIONS, PINESCRIPT, THINKSCRIPT, ScriptRecord
from .polite import PoliteSession, RobotsCache, RobotsDisallowed
from .sources.forum import ForumSource
from .sources.github import (
    GitHubError,
    GitHubSource,
    PERMISSIVE_LICENSES,
    SkippedRepository,
    detect_language,
)
from .sources.thinkorswim import (
    ThinkorswimSource,
    extract_thinkscript,
    share_id,
)
from .sources.tradingview import (
    TermsNotAccepted,
    TradingViewSource,
    extract_pine_source,
)
from .store import ScriptStore

__all__ = [
    "EXTENSIONS",
    "PINESCRIPT",
    "THINKSCRIPT",
    "CodeCandidate",
    "ForumSource",
    "GitHubError",
    "GitHubSource",
    "PERMISSIVE_LICENSES",
    "PoliteSession",
    "RobotsCache",
    "RobotsDisallowed",
    "ScriptRecord",
    "ScriptStore",
    "SkippedRepository",
    "TermsNotAccepted",
    "ThinkorswimSource",
    "TradingViewSource",
    "classify",
    "code_candidates",
    "declaration",
    "detect_language",
    "extract_pine_source",
    "extract_thinkscript",
    "input_names",
    "is_probably_commercial",
    "looks_like_pinescript",
    "looks_like_thinkscript",
    "looks_paywalled",
    "next_page_url",
    "pine_version",
    "share_id",
    "strip_comments",
    "thinkscript_kind",
    "thinkscript_pane",
]
