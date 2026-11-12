"""Static analysis of a strategy's code for look-ahead bias. No LLM, no network.

A port of ``check_lookahead.py`` from the papers repository
(``.claude/skills/check-strategy/scripts/check_lookahead.py``, 2026-11-08), so
the harness can run the same rules on every backtest instead of only when a
reviewer invokes the skill. The six ``check_*`` functions below are that file's,
unchanged; what this module adds is

* :func:`analyse` -- the report the script printed, as a dict;
* :func:`strategy_source` -- the code to analyse, recovered from the running
  process: a strategy is a file, a notebook cell, or (on the site and on the
  catalogue's server) a string handed to ``exec``, and the harness only ever
  receives its classes.

The rules, as in the script: a hard error (``lookahead_*``, ``unauthorized_*``)
is a read of data the strategy could not have had; a ``warning_*`` is a pattern
that is correct in some uses and wrong in others, and needs a reader.
"""
from __future__ import annotations

import __future__
import linecache
import os
import re
import sys


def check_positive_indices(code: str) -> list[dict]:
    """Find data feed accesses with positive indices (future data)."""
    issues = []
    pattern = re.compile(
        r"((?:self\.)?(?:data\w*|datas\[\d+\])\.(?:close|open|high|low|volume|datetime))"
        r"\[(\d+)\]"
    )
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for m in pattern.finditer(line):
            idx = int(m.group(2))
            if idx > 0:
                issues.append({
                    "line": i,
                    "code": m.group(0),
                    "index": idx,
                    "reason": f"Positive index [{idx}] accesses future data",
                })
    return issues


def check_unauthorized_datasets(code: str, allowed_datasets: list[str]) -> list[dict]:
    """Find pwb_ds.load_dataset() calls with datasets not in the allowed list."""
    issues = []
    pattern = re.compile(r"""load_dataset\(\s*['"]([^'"]+)['"]\s*""")
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for m in pattern.finditer(line):
            ds = m.group(1)
            if ds not in allowed_datasets:
                issues.append({
                    "line": i,
                    "dataset": ds,
                    "reason": f"Dataset '{ds}' is not in the allowed list",
                })
    return issues


def check_merge_asof_without_lag(code: str) -> list[dict]:
    """Detect merge_asof on quarterly data without an explicit reporting lag.

    Quarterly datasets use fiscal quarter end as the date. A backward merge_asof
    alone uses data as of the quarter end — before it was actually filed.
    An explicit lag (e.g. pd.DateOffset(months=3)) must be applied to the
    quarterly dates BEFORE the merge.
    """
    issues = []
    lines = code.splitlines()

    # Check if code loads any quarterly dataset
    quarterly_datasets = [
        "Stocks-Quarterly-BalanceSheet",
        "Stocks-Quarterly-IncomeStatement",
        "Stocks-Quarterly-CashFlow",
        "Stocks-Quarterly-Earnings",
    ]
    loads_quarterly = any(
        ds in code for ds in quarterly_datasets
    )
    if not loads_quarterly:
        return issues

    # Check if code uses merge_asof
    has_merge_asof = "merge_asof" in code

    if not has_merge_asof:
        return issues

    # Check if code applies a date lag/offset to quarterly data before merging.
    # We need specific patterns that indicate a REPORTING LAG, not just any date math.
    # MonthEnd() is too broad — it's commonly used for date normalization, not lagging.
    lag_patterns = [
        r"DateOffset\s*\(\s*months\s*=\s*[1-9]",  # pd.DateOffset(months=N) with N>=1
        r"timedelta.*days.*9[0-9]",                 # timedelta(days=90+)
        r'Timedelta\s*\(\s*["\']?\s*9\d+\s*[Dd]',  # pd.Timedelta("90D"+)
        r"\+\s*pd\.DateOffset",                      # Adding a DateOffset (lag)
    ]
    # Also check if reported_date from Earnings is used as the merge key
    uses_reported_date = bool(re.search(
        r"""reported_date.*(?:merge|asof|left_on|right_on)"""
        r"""|(?:merge|asof|left_on|right_on).*reported_date""",
        code,
    ))
    has_lag = uses_reported_date or any(re.search(pat, code) for pat in lag_patterns)

    if not has_lag:
        # Find the merge_asof line(s) to report
        for i, line in enumerate(lines, 1):
            if "merge_asof" in line:
                issues.append({
                    "line": i,
                    "code": line.strip(),
                    "reason": (
                        "merge_asof on quarterly data without explicit reporting lag. "
                        "Quarterly dataset dates are fiscal quarter ends, not filing dates. "
                        "Add a lag (e.g. pd.DateOffset(months=3)) to quarterly dates before merging, "
                        "or use the reported_date column from Earnings data."
                    ),
                })
    return issues


def check_forward_shift_usage(code: str) -> list[dict]:
    """Detect shift(-n) or iloc-based forward access that may indicate label leakage.

    Forward shifts are legitimate ONLY for computing training labels. Flag them
    as warnings so the reviewer can verify they are properly contained.
    """
    issues = []
    pattern = re.compile(r"\.shift\(\s*-\s*(\d+)\s*\)")
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for m in pattern.finditer(line):
            shift_val = int(m.group(1))
            if shift_val > 0:
                issues.append({
                    "line": i,
                    "code": stripped[:120],
                    "shift": -shift_val,
                    "reason": (
                        f"shift(-{shift_val}) computes future values. "
                        "Verify this is ONLY used for training labels and that "
                        "training data respects the train/test split boundary."
                    ),
                })
    return issues


def check_normalization_date_filter(code: str) -> list[dict]:
    """Detect cross-sectional normalization restricted to training dates only.

    If z-score / rank stats are computed only for dates <= split_date,
    they won't be available during OOT scoring, causing a train/test mismatch.
    """
    issues = []
    lines = code.splitlines()

    # Look for patterns where stats/normalization is date-filtered
    zscore_patterns = [
        r"zscore",
        r"z_score",
        r"cross.?sectional.*(?:mean|std|stat)",
        r"cs_stats",
    ]
    has_normalization = any(
        re.search(pat, code, re.IGNORECASE) for pat in zscore_patterns
    )
    if not has_normalization:
        return issues

    # Check for date filters that restrict normalization stats to training period only.
    # Only flag lines that appear to be filtering dates for stat computation, not
    # lines that guard trading logic (e.g. "only trade after split_date" is fine).
    stat_context_patterns = [
        r"stat", r"mean", r"std", r"zscore", r"z_score", r"norm",
        r"sorted", r"mes_sorted", r"month.*end", r"all_mes",
    ]
    filter_patterns = [
        (r"<=\s*self\.\w*split", "stats filtered by split date"),
        (r"<=\s*self\.\w*train", "stats filtered by training boundary"),
    ]
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Only flag if the line is in a stats/normalization context (not trading logic)
        line_lower = line.lower()
        in_stat_context = any(re.search(p, line_lower) for p in stat_context_patterns)
        if not in_stat_context:
            continue
        # Exclude trading logic lines (rebalance guards, signal processing)
        trading_keywords = ["rebalanc", "signal", "trade", "order", "position"]
        if any(kw in line_lower for kw in trading_keywords):
            continue
        for pat, desc in filter_patterns:
            if re.search(pat, line):
                issues.append({
                    "line": i,
                    "code": stripped[:120],
                    "reason": (
                        f"Possible train/test normalization mismatch: {desc}. "
                        "If cross-sectional stats are only computed for training months, "
                        "OOT scoring will use unnormalized features while the model "
                        "expects normalized inputs. Cross-sectional normalization at "
                        "time T is NOT forward-looking and should cover all months."
                    ),
                })
    return issues


_BEGIN_OFFSETS = r"B?(?:Month|Quarter|Year)Begin|SemiMonthBegin"
_END_OFFSETS = r"B?(?:Month|Quarter|Year)End|SemiMonthEnd"
_OFFSET_ARITHMETIC = re.compile(
    r"([-+])\s*(?:[A-Za-z_]\w*\.)*"
    r"(?P<name>" + _BEGIN_OFFSETS + "|" + _END_OFFSETS + r"|Week)"
    r"\((?P<args>[^()]*)\)"
)


def _offset_n(args: str) -> int | None:
    """The offset's `n`: 1 when absent, None when it is not an integer literal."""
    kw = re.search(r"\bn\s*=\s*([^,]+)", args)
    first = args.split(",", 1)[0].strip()
    raw = kw.group(1).strip() if kw else ("" if (not first or "=" in first) else first)
    if raw == "":
        return 1
    return int(raw) if re.fullmatch(r"[-+]?\d+", raw) else None


def check_anchored_calendar_offsets(code: str) -> list[dict]:
    """Anchored pandas offsets whose result depends on whether the date is on the anchor.

    `d - MonthBegin(1)` is the first of the previous month when `d` is a 1st, and the
    first of the CURRENT month otherwise: on a first session that falls on the 2nd or 3rd
    (weekends; the harness's bars are weekdays) "the month just ended" becomes the month
    that has just started, i.e. the future. `d + MonthBegin(0)` (and `- MonthBegin(0)`,
    which also rolls forward) has the same split. Both are errors: write the intent with
    Period arithmetic, `d.to_period("M") - 1`, `d.replace(day=1) - pd.Timedelta(days=1)`,
    or, on a date known to be a 1st, `pd.DateOffset(months=1)`.

    `d + MonthEnd(1)` is this month's end, except on a month's last day, where it is the
    next one; `Week(weekday=k)` jumps a full week when `d` is already that weekday. Those
    are correct on a date already on the anchor (a month-end index) and are warnings.
    """
    issues = []
    for i, line in enumerate(code.splitlines(), 1):
        body = line.split("#", 1)[0]
        if not body.strip():
            continue
        for m in _OFFSET_ARITHMETIC.finditer(body):
            sign = 1 if m.group(1) == "+" else -1
            name, args = m.group("name"), m.group("args")
            n = _offset_n(args)
            step = None if n is None else sign * n
            if re.fullmatch(_BEGIN_OFFSETS, name):
                if (step is not None and step <= 0) or (step is None and sign < 0):
                    issues.append({
                        "type": "lookahead_calendar_offset",
                        "line": i,
                        "code": line.strip()[:120],
                        "reason": (
                            f"{m.group(0).strip()} depends on whether the date is a period start: "
                            "on a 1st it gives the previous period, on any other day the current "
                            "one. Use d.to_period('M') - 1, d.replace(day=1) - pd.Timedelta(days=1), "
                            "or pd.DateOffset(months=1) on a date known to be a 1st."
                        ),
                    })
                elif step is None:
                    issues.append({
                        "type": "warning_calendar_offset",
                        "line": i,
                        "code": line.strip()[:120],
                        "reason": (
                            f"{m.group(0).strip()} with a variable n: a zero n rolls an off-anchor "
                            "date forward to the next period. Verify the date is a period start."
                        ),
                    })
            elif name == "Week":
                if "weekday" in args and step != 0:
                    issues.append({
                        "type": "warning_calendar_offset",
                        "line": i,
                        "code": line.strip()[:120],
                        "reason": (
                            f"{m.group(0).strip()} skips a full week when the date is already that "
                            "weekday. Use Week(weekday=k).rollback(d) for the latest such day, "
                            "or verify the date can never fall on it."
                        ),
                    })
            elif (step is None and sign > 0) or (step is not None and step >= 1):
                issues.append({
                    "type": "warning_calendar_offset",
                    "line": i,
                    "code": line.strip()[:120],
                    "reason": (
                        f"{m.group(0).strip()} gives the current period's end, except on its last "
                        "day, where it gives the next one. Verify the date is already a period "
                        "end, or use + MonthEnd(0) for the current period's end."
                    ),
                })
    return issues


# --------------------------------------------------------------------------- #
# What the script's main() did, as a function
# --------------------------------------------------------------------------- #


def analyse(code: str, allowed_datasets: list[str] | None = None) -> dict:
    """``{"errors_count", "warnings_count", "issues"}`` -- the script's report.

    ``allowed_datasets`` is the README's ``Datasets`` field in the papers
    repository; without it (the harness has no such list) the dataset rule is
    not run, as in the script.
    """
    issues = []
    for issue in check_positive_indices(code):
        issues.append({"type": "lookahead_positive_index", **issue})
    if allowed_datasets:
        for issue in check_unauthorized_datasets(code, allowed_datasets):
            issues.append({"type": "unauthorized_dataset", **issue})
    for issue in check_merge_asof_without_lag(code):
        issues.append({"type": "lookahead_unlagged_fundamentals", **issue})
    for issue in check_forward_shift_usage(code):
        issues.append({"type": "warning_forward_shift", **issue})
    for issue in check_normalization_date_filter(code):
        issues.append({"type": "warning_normalization_mismatch", **issue})
    issues.extend(check_anchored_calendar_offsets(code))
    errors = [i for i in issues if not i["type"].startswith("warning_")]
    return {
        "errors_count": len(errors),
        "warnings_count": len(issues) - len(errors),
        "issues": issues,
    }


# --------------------------------------------------------------------------- #
# Finding the code
# --------------------------------------------------------------------------- #

_PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_ours(filename: str) -> bool:
    """A frame or class of pwb_toolbox itself: the harness, not the strategy."""
    try:
        return os.path.abspath(filename).startswith(_PACKAGE_DIR + os.sep)
    except (TypeError, ValueError):
        return False


def _read_file(filename: str) -> str | None:
    if not filename or not os.path.isfile(filename):
        return None
    try:
        with open(filename, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _class_file(cls) -> str | None:
    """Where the class's own methods were compiled, or ``None``."""
    if cls is None:
        return None
    for value in vars(cls).values():
        func = getattr(value, "__func__", value)
        code = getattr(func, "__code__", None)
        if code is not None:
            return code.co_filename
    return None


def _module_frame(frame):
    """The ``<module>`` frame of the file ``frame`` runs in, walking outwards."""
    filename = frame.f_code.co_filename
    found = None
    while frame is not None and frame.f_code.co_filename == filename:
        if frame.f_code.co_name == "<module>":
            found = frame
        frame = frame.f_back
    return found


_FUTURE_FLAGS = (0, __future__.annotations.compiler_flag)


def _compiles_to(candidate: str, code) -> bool:
    for flags in _FUTURE_FLAGS:
        try:
            compiled = compile(candidate, code.co_filename, "exec", flags=flags, dont_inherit=True)
        except (SyntaxError, ValueError, TypeError):
            return False
        if compiled.co_code == code.co_code and compiled.co_names == code.co_names:
            return True
    return False


def _exec_source(module_frame) -> str | None:
    """The string ``exec`` ran, found among the variables of the frames above it.

    ``exec(code, namespace)`` keeps no copy of ``code``: the frame it creates has
    a code object and a filename of ``"<string>"``. The string is still alive
    in whoever called ``exec`` -- the papers' ``Backtester.backtest(code)``, the
    site's ``exec(code, namespace)`` -- and the one that compiles to the very
    bytecode running is the source, not a guess.
    """
    code = module_frame.f_code
    frame = module_frame.f_back
    depth = 0
    while frame is not None and depth < 8:
        for value in list(frame.f_locals.values()):
            if isinstance(value, str) and len(value) > 40 and _compiles_to(value, code):
                return value
        frame = frame.f_back
        depth += 1
    return None


def strategy_source(strategy_cls=None, indicator_cls=None, caller=None) -> list[tuple[str, str]]:
    """``[(origin, source), ...]`` -- the code a backtest runs, as far as it can be found.

    ``caller`` is the frame that called ``run_strategy``. Looked for, in order:

    1. the script that called the harness (its ``<module>`` frame): read from
       its file, from ``linecache`` (notebook cells register there), or
       recovered from the caller of ``exec`` (:func:`_exec_source`);
    2. the files the strategy and indicator classes were defined in, when
       they are not that script and not pwb_toolbox itself.

    An empty list means nothing could be read: the check then says so rather
    than passing.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    frame = caller
    while frame is not None and _is_ours(frame.f_code.co_filename):
        frame = frame.f_back
    module = _module_frame(frame) if frame is not None else None
    if module is not None:
        filename = module.f_code.co_filename
        source = _read_file(filename)
        origin = filename
        if source is None:
            lines = linecache.getlines(filename)
            source = "".join(lines) if lines else None
        if source is None:
            source = _exec_source(module)
            origin = "exec"
        if source is not None:
            found.append((origin, source))
            seen.add(filename)

    for cls in (strategy_cls, indicator_cls):
        filename = _class_file(cls)
        if not filename or filename in seen or _is_ours(filename):
            continue
        seen.add(filename)
        source = _read_file(filename)
        if source is None:
            lines = linecache.getlines(filename)
            source = "".join(lines) if lines else None
        if source is not None:
            found.append((filename, source))
    return found


def main() -> int:
    """``python -m pwb_toolbox.backtesting.lookahead <strategy.py> [datasets_csv]``."""
    import json

    if len(sys.argv) < 2:
        print("Usage: python -m pwb_toolbox.backtesting.lookahead <strategy_path> [allowed_datasets_csv]",
              file=sys.stderr)
        return 1
    path = sys.argv[1]
    code = _read_file(path)
    if code is None:
        print(json.dumps({"error": f"File not found: {path}"}))
        return 1
    allowed = [d.strip() for d in sys.argv[2].split(",") if d.strip()] if len(sys.argv) >= 3 else None
    report = {"file": path, **analyse(code, allowed)}
    print(json.dumps(report, indent=2))
    return 1 if report["errors_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
