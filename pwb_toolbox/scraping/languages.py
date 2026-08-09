"""Recognising and parsing PineScript and thinkScript source.

The detection helpers exist because file extensions are not trustworthy: a
``.ts`` file is far more likely to be TypeScript than thinkScript, and plenty
of published PineScript lives in ``.txt`` files. Every candidate file is
therefore checked against the content heuristics below before it is kept.
"""

import re

from .models import PINESCRIPT, THINKSCRIPT

_VERSION_RE = re.compile(r"^\s*//\s*@version\s*=\s*(\d+)", re.MULTILINE)
_DECLARATION_RE = re.compile(
    r"^\s*(?:var\s+)?(strategy|indicator|study|library)\s*\(", re.MULTILINE
)
_INPUT_ASSIGN_RE = re.compile(r"^\s*(\w+)\s*=\s*input(?:\.\w+)?\s*\(", re.MULTILINE)
_TITLE_KWARG_RE = re.compile(r"""title\s*=\s*(["'])(.*?)\1""", re.DOTALL)
_ANY_STRING_RE = re.compile(r"""(["'])(.*?)\1""", re.DOTALL)

_TYPESCRIPT_MARKERS = (
    "import ",
    "export ",
    "function ",
    "const ",
    "let ",
    "=>",
    "interface ",
    "console.log",
)


def _strip_line_comment(line: str) -> str:
    """Drop a trailing ``//`` comment, ignoring ``//`` inside string literals."""
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "/" and line[i + 1 : i + 2] == "/":
            return line[:i]
        i += 1
    return line


def strip_comments(code: str) -> str:
    """Remove line comments while preserving line structure."""
    return "\n".join(_strip_line_comment(line) for line in code.splitlines())


def pine_version(code: str) -> int | None:
    """Return the ``//@version=N`` annotation, or ``None`` when absent."""
    match = _VERSION_RE.search(code)
    return int(match.group(1)) if match else None


def _balanced_args(code: str, open_index: int) -> str:
    """Return the text between the parenthesis at ``open_index`` and its match."""
    depth = 0
    quote = None
    for i in range(open_index, len(code)):
        ch = code[i]
        if quote is not None:
            if ch == "\\":
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return code[open_index + 1 : i]
    return code[open_index + 1 :]


def declaration(code: str) -> tuple[str, str] | None:
    """Return ``(kind, title)`` for a script's declaration statement.

    ``kind`` is normalised so the legacy v3/v4 ``study`` becomes ``indicator``.
    Returns ``None`` when no declaration is found.
    """
    stripped = strip_comments(code)
    match = _DECLARATION_RE.search(stripped)
    if match is None:
        return None

    kind = match.group(1)
    kind = "indicator" if kind == "study" else kind
    args = _balanced_args(stripped, match.end() - 1)

    title_match = _TITLE_KWARG_RE.search(args)
    if title_match is None:
        title_match = _ANY_STRING_RE.search(args)
    title = title_match.group(2).strip() if title_match else ""
    return kind, title


def input_names(code: str) -> list[str]:
    """Names of variables assigned from an ``input`` call, in source order."""
    seen = []
    for name in _INPUT_ASSIGN_RE.findall(strip_comments(code)):
        if name not in seen:
            seen.append(name)
    return seen


def looks_like_pinescript(code: str) -> bool:
    """Heuristic content check for PineScript."""
    score = 0
    if pine_version(code) is not None:
        score += 3
    if declaration(code) is not None:
        score += 3
    for marker in ("ta.", "strategy.", "plotshape(", "plot(", "request.security("):
        if marker in code:
            score += 1
    return score >= 3


_COMMERCIAL_MARKERS = (
    "all rights reserved",
    "paid members only",
    "premium members",
    "subscription required",
    "license key",
    "licence key",
    "unauthorized distribution",
    "unauthorised distribution",
    "do not share",
    "do not redistribute",
    "invite-only script",
    "invite only script",
)


def is_probably_commercial(code: str) -> bool:
    """Flag code that advertises itself as paid, licensed or non-redistributable.

    Both the TradingView and thinkorswim communities mix freely shared studies
    with commercial ones, and the paid scripts usually say so in a header
    comment. This is a coarse filter -- it reads comments, not intent -- but it
    keeps the obvious cases out of a corpus meant for reuse.
    """
    lowered = code.lower()
    return any(marker in lowered for marker in _COMMERCIAL_MARKERS)


def looks_like_thinkscript(code: str) -> bool:
    """Heuristic content check for thinkScript.

    Rejects TypeScript outright, since both languages claim the ``.ts``
    extension and TypeScript is overwhelmingly more common on GitHub.
    """
    if any(marker in code for marker in _TYPESCRIPT_MARKERS):
        return False

    score = 0
    lowered = code.lower()
    if re.search(r"^\s*declare\s+(lower|upper|on_volume)\s*;", lowered, re.MULTILINE):
        score += 3
    if re.search(r"^\s*plot\s+\w+\s*=", code, re.MULTILINE):
        score += 2
    if re.search(r"^\s*def\s+\w+\s*=", code, re.MULTILINE):
        score += 1
    if re.search(r"^\s*input\s+\w+\s*=", code, re.MULTILINE):
        score += 1
    for marker in ("AddLabel(", "AddOrder(", "AddChartBubble(", "AddCloud("):
        if marker in code:
            score += 2
    return score >= 3


def thinkscript_kind(code: str) -> str:
    """``"strategy"`` when the study places orders, else ``"indicator"``.

    thinkScript has no declaration keyword separating the two the way Pine's
    ``strategy()``/``indicator()`` does; placing orders via ``AddOrder`` is what
    actually makes a study a strategy.
    """
    return "strategy" if "AddOrder(" in code else "indicator"


def thinkscript_pane(code: str) -> str | None:
    """Which chart pane the study declares, or ``None`` when it does not."""
    match = re.search(
        r"^\s*declare\s+(lower|upper|on_volume)\s*;", code.lower(), re.MULTILINE
    )
    return match.group(1) if match else None


def classify(code: str) -> str | None:
    """Identify ``code`` as thinkScript or PineScript, or ``None`` if neither.

    thinkScript is checked first: this is used mostly on thinkorswim sources,
    and the two predicates are mutually exclusive in practice anyway.
    """
    if looks_like_thinkscript(code):
        return THINKSCRIPT
    if looks_like_pinescript(code):
        return PINESCRIPT
    return None
