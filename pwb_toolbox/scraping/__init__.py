"""Collect PineScript and thinkScript source code from the web.

PineScript is TradingView's language and thinkScript is thinkorswim's; they
are unrelated dialects and are detected, parsed and stored separately here.

The intended entry point is :class:`~pwb_toolbox.scraping.sources.github.GitHubSource`,
which reads open-source repositories through the GitHub API and keeps each
repository's license attached to the code it yields.
"""

from .languages import (
    declaration,
    input_names,
    is_probably_commercial,
    looks_like_pinescript,
    looks_like_thinkscript,
    pine_version,
    strip_comments,
)
from .models import EXTENSIONS, PINESCRIPT, THINKSCRIPT, ScriptRecord
from .polite import PoliteSession, RobotsCache, RobotsDisallowed
from .sources.github import (
    GitHubError,
    GitHubSource,
    PERMISSIVE_LICENSES,
    SkippedRepository,
    detect_language,
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
    "TradingViewSource",
    "declaration",
    "detect_language",
    "extract_pine_source",
    "input_names",
    "is_probably_commercial",
    "looks_like_pinescript",
    "looks_like_thinkscript",
    "pine_version",
    "strip_comments",
]
