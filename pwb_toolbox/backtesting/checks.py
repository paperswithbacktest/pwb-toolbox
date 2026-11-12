"""Automatic checks the harness computes on every backtest, like a CI run.

``run_strategy`` attaches the result to the strategy it returns, as
``strategy.checks`` and ``strategy.run_report["checks"]``, and prints it on one
``Checks:`` line. Whoever posts the run to paperswithbacktest.com sends it
along with the NAV, unchanged::

    {"computedBy": "harness", "toolboxVersion": "0.1.49", "computedAt": "<iso>",
     "items": [{"id": "lookahead", "status": "pass|fail|warn",
                "summary": "<one line>", "detail": {...}}, ...]}

Four checks, each a rule with its thresholds declared below:

* ``lookahead`` -- static analysis of the strategy's code (``lookahead.py``,
  the papers repository's ``check_lookahead``): a read of future data fails,
  a pattern that needs a reader warns.
* ``universe`` -- a point-in-time universe passes; a fixed list of today's
  stocks replayed over a long history warns (survivorship bias).
* ``execution`` -- from the run's own order journal: an order filled on the
  bar whose data produced it (cheat-on-close, cheat-on-open) fails.
* ``costs`` -- the share of the traded value charged the default floor rather
  than a measured spread; an equity at the floor has no reason to be there.

A check never stops a backtest: if computing one raises, it is reported as
``warn`` with the reason, and the run goes on. ``PWB_HARNESS_CHECKS=0`` in the
environment switches the whole thing off.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np

from ..engine import load as _load_engine
from . import lookahead as _lookahead

bt = _load_engine()

CHECK_IDS = ("lookahead", "universe", "execution", "costs")
ENV_SWITCH = "PWB_HARNESS_CHECKS"

# -- universe ---------------------------------------------------------------
#: A fixed list of single stocks replayed over at least this many years warns:
#: the names were picked among today's survivors. Measured on the
#: point-in-time table, 56 % of the 500 names ranked at the end of 2005 are not
#: in today's list, 39 % at the end of 2015, 34 % at the end of 2020.
UNIVERSE_SPAN_YEARS = 5.0
#: A fixed basket of at least this many coins is a cross-section of survivors
#: too: the crypto feed holds no dead token. One or two (BTC, ETH) are the
#: asset itself, not a selection.
UNIVERSE_CRYPTO_BASKET = 3
#: A point-in-time name whose last real bar is this long before the end of the
#: panel counts as delisted (bought out, bankrupt, gone).
DELISTED_GAP_DAYS = 30

# -- execution --------------------------------------------------------------
#: Fills allowed on the bar whose data produced the order. None: the harness
#: executes at the next bar's open, and any fill on the signal bar means the
#: strategy traded at a price it read before deciding.
EXECUTION_SAME_BAR_TOLERANCE = 0

# -- costs ------------------------------------------------------------------
#: Share of the traded value at the default floor, on names that have a
#: measured spread to be charged (stocks, ETFs and the other US-listed
#: securities of the cost table), above which the check fails; and above which
#: it warns. 0.1.47 put every member of ``["sp500"]`` there: 100 %.
COSTS_DEFAULT_FAIL_SHARE = 0.20
COSTS_DEFAULT_WARN_SHARE = 0.05

# How a feed's repository maps to an asset class.
_REPO_CLASS = {
    "Stocks-Daily-Price": "stock",
    "Preferreds-Daily-Price": "security",
    "Warrants-Daily-Price": "security",
    "StructuredProducts-Daily-Price": "security",
    "ETFs-Daily-Price": "etf",
    "Indices-Daily-Price": "index",
    "Forex-Daily-Price": "forex",
    "Cryptocurrencies-Daily-Price": "crypto",
    "Commodities-Daily-Price": "commodity",
    "Bonds-Daily-Price": "bond",
}
_SUFFIX_CLASS = {
    "CRP": "crypto",
    "CRYPTO": "crypto",
    "STK": "stock",
    "CMD": "commodity",
    "IDX": "index",
    "ETF": "etf",
    "FXR": "forex",
    "BND": "bond",
}
#: Classes listed in survivor-only feeds, where a fixed list is a selection.
SURVIVOR_CLASSES = ("stock", "security")
#: Classes the US equity cost table measures: a default spread there is a defect.
MEASURED_CLASSES = ("stock", "security", "etf")


# --------------------------------------------------------------------------- #
# Asset classes
# --------------------------------------------------------------------------- #

_INDEX_ROUTES: dict | None = None


def _index_routes() -> dict:
    """``{symbol: repository}`` from the catalogue index, ETF first; loaded once.

    Only consulted for a name ``get_pricing`` did not report a route for (an
    older loader, a patched one). The same tie-break as ``get_pricing``.
    """
    global _INDEX_ROUTES
    if _INDEX_ROUTES is None:
        try:
            import pwb_toolbox.datasets as pwb_ds

            universe = pwb_ds.load_dataset("Universe-Daily-Price")
            _INDEX_ROUTES = {
                str(k): str(v).split("/")[-1]
                for k, v in pwb_ds._bare_symbol_routes(universe).items()
            }
        except Exception:  # noqa: BLE001 -- a check never stops a run
            _INDEX_ROUTES = {}
    return _INDEX_ROUTES


def asset_class(name: str, routes: dict | None = None, members=frozenset()) -> str:
    """``stock``, ``etf``, ``index``, ``forex``, ``crypto``... or ``unknown``.

    A member of a point-in-time universe is a stock by construction; a suffix
    says what the caller meant; otherwise the feed ``get_pricing`` read it from.
    """
    name = str(name)
    if name in members:
        return "stock"
    base = name
    if "." in name:
        base, _, suffix = name.rpartition(".")
        known = _SUFFIX_CLASS.get(suffix.upper())
        if known:
            return known
        base = base or name
    repo = (routes or {}).get(base) or (routes or {}).get(name)
    if repo is None:
        repo = _index_routes().get(base)
    if repo is None:
        return "unknown"
    return _REPO_CLASS.get(str(repo).split("/")[-1], "other")


# --------------------------------------------------------------------------- #
# What the run records
# --------------------------------------------------------------------------- #


def record_submissions(broker, created: dict) -> None:
    """Note the bar each order was submitted on: the bar of its signal.

    Installed on ``broker.submit`` like the harness's guards, because every
    order -- ``buy``, ``sell``, ``order_target_*``, ``close`` -- passes there,
    on both engines, while ``order.created.dt`` is only filled by backtrader.
    """
    original = broker.submit

    def submit(order, check=True):
        try:
            created[order.ref] = order.data.datetime[0]
        except Exception:  # noqa: BLE001
            pass
        return original(order, check=check)

    broker.submit = submit


def _day(stamp):
    """A bar's day as an integer, from an engine date number or a datetime."""
    if stamp is None:
        return None
    if isinstance(stamp, (int, float, np.floating, np.integer)):
        value = float(stamp)
        return int(value) if np.isfinite(value) and value > 0 else None
    if hasattr(stamp, "toordinal"):
        return stamp.toordinal()
    return None


class OrderJournal(bt.Analyzer):
    """Every completed fill, reduced to what the checks read.

    ``created`` -- ``{order.ref: date number of the submission bar}``, filled
    by :func:`record_submissions`. Kept as aggregates, not a list of fills: a
    daily book of two thousand names makes tens of thousands of them.
    """

    params = (("created", None),)

    def start(self):
        self.fills = 0
        self.same_bar = 0
        self.unmatched = 0
        self.examples = []
        self.exectypes = {}
        self.by_symbol = {}

    def notify_order(self, order):
        if order.status != order.Completed:
            return
        executed = order.executed
        size = float(executed.size or 0.0)
        if not size:
            return
        created = self.p.created if self.p.created is not None else {}
        signal = _day(created.pop(order.ref, None))
        filled = _day(getattr(executed, "dt", None))
        self.fills += 1
        try:
            kind = order.getordername()
        except Exception:  # noqa: BLE001
            kind = str(getattr(order, "exectype", "?"))
        self.exectypes[kind] = self.exectypes.get(kind, 0) + 1
        name = getattr(order.data, "_name", None) or "?"
        if signal is None or filled is None:
            self.unmatched += 1
        elif filled <= signal:
            self.same_bar += 1
            if len(self.examples) < 3:
                self.examples.append({
                    "symbol": name,
                    "date": bt.num2date(float(executed.dt)).date().isoformat()
                    if isinstance(executed.dt, (int, float)) else str(executed.dt),
                    "type": kind,
                })
        price = float(executed.price or 0.0)
        entry = self.by_symbol.setdefault(name, [0, 0.0, 0.0])
        entry[0] += 1
        entry[1] += abs(size * price)
        entry[2] += float(getattr(executed, "comm", 0.0) or 0.0)

    def get_analysis(self):
        return {
            "fills": self.fills,
            "same_bar": self.same_bar,
            "unmatched": self.unmatched,
            "examples": list(self.examples),
            "exectypes": dict(self.exectypes),
            "by_symbol": {
                k: {"fills": v[0], "value": v[1], "comm": v[2]} for k, v in self.by_symbol.items()
            },
        }


def broker_flags(broker) -> dict:
    """Cheat-on-close and cheat-on-open, as the broker of either engine holds them."""
    params = getattr(broker, "p", None)
    coc = getattr(broker, "_coc", None)
    if coc is None:
        coc = getattr(params, "coc", False)
    coo = getattr(broker, "_coo", None)
    if coo is None:
        coo = getattr(params, "coo", False)
    return {"coc": bool(coc), "coo": bool(coo)}


def universe_facts(symbols, present, routes: dict | None = None) -> dict:
    """What the ``universe`` check needs from the panel, read before any fill.

    ``present`` is ``run_strategy``'s row mask (``True`` where a symbol has a
    real bar). Computed at load time so the check does not keep the panel.
    """
    import pwb_toolbox.datasets as pwb_ds

    if isinstance(symbols, str):
        symbols = [symbols]
    asked = list(symbols)
    alias = next((s for s in asked if s in pwb_ds.PIT_UNIVERSES), None)
    frozen = "sp500-frozen" in asked
    _, _spec, added, explicit = pwb_ds._resolve_universe(asked)
    members = frozenset(added) - frozenset(explicit)
    columns = list(present.columns)
    index = present.index
    end = index.max() if len(index) else None
    mask = present.to_numpy(dtype=bool) if len(columns) else np.zeros((0, 0), dtype=bool)
    has = mask.any(axis=0) if mask.size else np.zeros(len(columns), dtype=bool)
    first = np.argmax(mask, axis=0) if mask.size else np.zeros(len(columns), dtype=int)
    last = (len(index) - 1 - np.argmax(mask[::-1], axis=0)) if mask.size else first
    position = {name: i for i, name in enumerate(columns)}

    loaded_members = [m for m in members if m in position and has[position[m]]]
    delisted = 0
    if end is not None:
        cutoff = end - np.timedelta64(DELISTED_GAP_DAYS, "D")
        for name in loaded_members:
            if index[last[position[name]]] < cutoff:
                delisted += 1

    named = {}
    for name in explicit:
        base = str(name).rpartition(".")[0] if "." in str(name) else str(name)
        feed = name if name in position else base
        start = None
        if feed in position and has[position[feed]]:
            start = index[first[position[feed]]]
        # Only a loaded name is classified: one without data cannot bias anything.
        cls = asset_class(name, routes) if start is not None else "unknown"
        named[str(name)] = {"class": cls, "first": start, "loaded": start is not None}
    return {
        "alias": alias,
        "frozen": frozen,
        "members": len(loaded_members),
        "delisted": delisted,
        "named": named,
        "end": end,
    }


# --------------------------------------------------------------------------- #
# The four checks
# --------------------------------------------------------------------------- #


def _item(check_id, status, summary, detail=None) -> dict:
    return {"id": check_id, "status": status, "summary": summary, "detail": detail or {}}


def _first_issue(issues):
    issue = issues[0]
    code = str(issue.get("code") or issue.get("dataset") or "").strip()
    if len(code) > 60:
        code = code[:57] + "..."
    where = f" (line {issue['line']})" if issue.get("line") else ""
    more = f" and {len(issues) - 1} more" if len(issues) > 1 else ""
    return f"{code}{where}{more}"


def check_lookahead(sources) -> dict:
    """``fail`` on a read of future data in the code, ``warn`` on a pattern to verify.

    ``sources`` -- ``[(origin, code)]`` from :func:`lookahead.strategy_source`.
    No source found is a ``warn``: nothing was checked, so nothing passed.
    """
    if not sources:
        return _item(
            "lookahead", "warn", "strategy source not available to the harness — not analysed",
            {"sources": []},
        )
    errors, warnings, analysed = [], [], []
    for origin, code in sources:
        report = _lookahead.analyse(code)
        label = "exec" if origin == "exec" else os.path.basename(str(origin))
        analysed.append({"source": label, "lines": code.count("\n") + 1})
        for issue in report["issues"]:
            issue = {**issue, "source": label}
            (warnings if issue["type"].startswith("warning_") else errors).append(issue)
    detail = {"sources": analysed, "errors": errors[:20], "warnings": warnings[:20],
              "errorsCount": len(errors), "warningsCount": len(warnings)}
    if errors:
        return _item("lookahead", "fail", f"future data read: {_first_issue(errors)}", detail)
    if warnings:
        noun = "pattern" if len(warnings) == 1 else "patterns"
        return _item("lookahead", "warn",
                     f"{len(warnings)} {noun} to verify: {_first_issue(warnings)}", detail)
    return _item("lookahead", "pass", "no future data read", detail)


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else ("es" if word.endswith(("x", "s")) else "s"))


def check_universe(facts: dict, membership=None) -> dict:
    """``warn`` for today's stocks replayed over ``UNIVERSE_SPAN_YEARS`` or more."""
    named = facts["named"]
    end = facts["end"]
    alias = facts["alias"]
    loaded = {k: v for k, v in named.items() if v["loaded"]}
    classes: dict[str, int] = {}
    for entry in loaded.values():
        classes[entry["class"]] = classes.get(entry["class"], 0) + 1
    prone = [k for k, v in loaded.items() if v["class"] in SURVIVOR_CLASSES]
    coins = [k for k, v in loaded.items() if v["class"] == "crypto"]
    if len(coins) >= UNIVERSE_CRYPTO_BASKET:
        prone += coins
    starts = [loaded[k]["first"] for k in prone if loaded[k]["first"] is not None]
    span = ((end - min(starts)).days / 365.25) if starts and end is not None else 0.0
    detail = {
        "alias": alias,
        "frozen": facts["frozen"],
        "pointInTimeNames": facts["members"],
        "delisted": facts["delisted"],
        "exited": len(getattr(membership, "out", {}) or {}) if membership is not None else 0,
        "named": len(loaded),
        "namedClasses": classes,
        "fixedSurvivorNames": sorted(prone)[:50],
        "fixedSurvivorCount": len(prone),
        "spanYears": round(span, 1),
        "thresholdYears": UNIVERSE_SPAN_YEARS,
    }
    pit = (
        f"point-in-time {alias}, {facts['members']} names, {facts['delisted']} delisted included"
        if alias else None
    )
    if prone and span >= UNIVERSE_SPAN_YEARS:
        stocks = sum(1 for k in prone if loaded[k]["class"] in SURVIVOR_CLASSES)
        what = " and ".join(
            p for p in (
                _plural(stocks, "stock") if stocks else "",
                _plural(len(prone) - stocks, "coin") if len(prone) > stocks else "",
            ) if p
        )
        if facts["frozen"]:
            summary = (f"sp500-frozen: today's members replayed over {span:.0f} years "
                       f"— survivorship bias")
        else:
            summary = f"fixed list of {what} over {span:.0f} years — today's names, survivorship bias"
        if pit:
            summary = f"{pit}; plus {summary}"
        return _item("universe", "warn", summary, detail)
    if pit:
        extra = f", plus {_plural(len(loaded), 'named symbol')}" if loaded else ""
        return _item("universe", "pass", pit + extra, detail)
    if not loaded:
        return _item("universe", "warn", "no symbol loaded — nothing to check", detail)
    if prone:
        return _item(
            "universe", "pass",
            f"fixed list of {_plural(len(prone), 'name')} over {span:.1f} years "
            f"— under the {UNIVERSE_SPAN_YEARS:.0f}-year threshold",
            detail,
        )
    if set(classes) == {"unknown"}:
        return _item("universe", "warn",
                     f"asset class of {_plural(len(loaded), 'symbol')} unknown — not checked", detail)
    listing = ", ".join(f"{n} {c}" for c, n in sorted(classes.items(), key=lambda kv: -kv[1]))
    return _item("universe", "pass", f"no single stocks: {listing}", detail)


def check_execution(journal: dict, flags: dict) -> dict:
    """``fail`` when a fill lands on the bar whose data produced its order."""
    fills = journal["fills"]
    same = journal["same_bar"]
    unmatched = journal["unmatched"]
    detail = {
        "fills": fills,
        "sameBarFills": same,
        "unmatchedFills": unmatched,
        "examples": journal["examples"],
        "orderTypes": journal["exectypes"],
        "cheatOnClose": flags.get("coc", False),
        "cheatOnOpen": flags.get("coo", False),
        "tolerance": EXECUTION_SAME_BAR_TOLERANCE,
    }
    if not fills:
        return _item("execution", "warn", "no order filled — nothing to check", detail)
    if same > EXECUTION_SAME_BAR_TOLERANCE:
        why = []
        if flags.get("coc"):
            why.append("cheat-on-close")
        if flags.get("coo"):
            why.append("cheat-on-open")
        reason = f" ({', '.join(why)})" if why else ""
        return _item("execution", "fail",
                     f"{same} of {fills} fills on their signal bar{reason}", detail)
    if unmatched == fills:
        return _item("execution", "warn", "signal bar of the fills unknown — not checked", detail)
    types = journal["exectypes"]
    if set(types) <= {"Market"}:
        summary = "signal at close, fill at next open"
    else:
        listing = ", ".join(f"{n} {t}" for t, n in sorted(types.items(), key=lambda kv: -kv[1]))
        summary = f"no fill on its signal bar ({listing})"
    return _item("execution", "pass", summary, detail)


def check_costs(journal: dict, schemes, policy, caller_commission=None,
                routes: dict | None = None, members=frozenset()) -> dict:
    """``fail`` when the traded value of measurable names sits at the default floor.

    The class of each name is judged here, from the feed it was read from, not
    from the cost module's own routing: 0.1.47's defect was that routing, and a
    check that reused it would have agreed with it.
    """
    traded = journal["by_symbol"]
    total = sum(v["value"] for v in traded.values())
    paid = sum(v["comm"] for v in traded.values())
    base = {
        "tradedNames": len(traded),
        "tradedValue": total,
        "commissionPaid": paid,
        "commissionBpOfValue": (paid / total * 1e4) if total else None,
        "failShare": COSTS_DEFAULT_FAIL_SHARE,
        "warnShare": COSTS_DEFAULT_WARN_SHARE,
    }
    if schemes is None:
        rate = caller_commission
        shown = f"{float(rate) * 1e4:g} bp" if isinstance(rate, (int, float)) else str(rate)
        return _item("costs", "warn",
                     f"flat commission set by the strategy ({shown}) — measured spreads not applied",
                     {**base, "mode": "caller", "commission": rate})
    if not traded:
        return _item("costs", "warn", "no order filled — nothing to check", {**base, "mode": "measured"})

    sources = {"measured": [0, 0.0], "estimated": [0, 0.0], "default": [0, 0.0], "unpriced": [0, 0.0]}
    unexplained_names, unexplained_value = [], 0.0
    explained_classes: dict[str, int] = {}
    default_rates = []
    for name, entry in traded.items():
        scheme = schemes.get(name)
        cost = getattr(scheme, "pwb_cost", None)
        if cost is None:
            bucket = "unpriced"
        elif cost.source in ("measured", "extrapolated"):
            bucket = "measured"
        elif cost.source == "roll":
            bucket = "estimated"
        else:
            bucket = "default"
            default_rates.append(float(cost.half_spread))
            cls = asset_class(name, routes, members)
            if cls in MEASURED_CLASSES:
                unexplained_names.append(name)
                unexplained_value += entry["value"]
            else:
                explained_classes[cls] = explained_classes.get(cls, 0) + 1
        sources[bucket][0] += 1
        sources[bucket][1] += entry["value"]
    share = unexplained_value / total if total else 0.0
    measured_n, measured_v = sources["measured"]
    detail = {
        **base,
        "mode": (policy or {}).get("mode", "measured"),
        "names": {k: v[0] for k, v in sources.items()},
        "valueShare": {k: (v[1] / total if total else 0.0) for k, v in sources.items()},
        "unexplainedDefaultShare": share,
        "unexplainedDefaultNames": sorted(unexplained_names)[:50],
        "explainedDefaultClasses": explained_classes,
        "defaultHalfSpreadBp": (float(np.median(default_rates)) * 1e4) if default_rates else None,
        "strategyCommission": {
            k: (policy or {}).get(k) for k in ("floor_perc", "floor_fixed", "raised_symbols", "calls")
        } if (policy or {}).get("calls") else None,
    }
    n = len(traded)
    head = f"{measured_n} of {n} traded names at measured spread"
    if share > COSTS_DEFAULT_FAIL_SHARE or share > COSTS_DEFAULT_WARN_SHARE:
        bp = detail["defaultHalfSpreadBp"] or 1.0
        status = "fail" if share > COSTS_DEFAULT_FAIL_SHARE else "warn"
        return _item("costs", status,
                     f"{head} — default {bp:g} bp on {share:.0%} of traded value", detail)
    calls = (policy or {}).get("calls") or []
    raised = (policy or {}).get("raised_symbols", 0)
    if calls and raised:
        floor = (policy or {}).get("floor_perc") or 0.0
        fixed = (policy or {}).get("floor_fixed") or 0.0
        what = f"{floor * 1e4:g} bp" if floor else f"{fixed:g} per unit"
        return _item("costs", "warn",
                     f"{head}; the strategy sets its own commission ({what}) on {raised} of them",
                     detail)
    summary = f"{head} ({measured_v / total:.0%} of traded value)" if total else head
    if explained_classes:
        listing = ", ".join(f"{c}" for c in sorted(explained_classes))
        summary += f"; {sum(explained_classes.values())} at the floor ({listing}: no cost table)"
    return _item("costs", "pass", summary, detail)


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def enabled() -> bool:
    return os.getenv(ENV_SWITCH, "1").strip().lower() not in ("0", "false", "no", "off")


def toolbox_version() -> str | None:
    """The version of the code running, not of whatever the metadata says is installed."""
    try:
        import pwb_toolbox

        return getattr(pwb_toolbox, "__version__", None)
    except Exception:  # noqa: BLE001
        return None


def _jsonable(value):
    """Plain JSON: numpy scalars unwrapped, dates as ISO, NaN and infinities as null."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        return [_jsonable(v) for v in items]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _safely(check_id, fn) -> dict:
    try:
        return _jsonable(fn())
    except Exception as exc:  # noqa: BLE001 -- a check never stops a backtest
        reason = f"{type(exc).__name__}: {exc}"
        return _item(check_id, "warn", f"check could not run — {reason}"[:200], {"error": reason[:1000]})


def compute(context: dict) -> dict:
    """The ``checks`` block, from what ``run_strategy`` gathered.

    ``context`` keys: ``sources`` (or ``sources_error``), ``facts`` (or
    ``facts_error``), ``membership``, ``members``, ``journal``, ``flags``,
    ``schemes``, ``policy``, ``caller_commission``, ``routes``. A missing piece makes its
    check a ``warn`` with the reason, never an exception.
    """

    def need(key):
        error = context.get(f"{key}_error")
        if error is not None:
            raise RuntimeError(error)
        if key not in context or context[key] is None:
            raise RuntimeError(f"{key} was not recorded")
        return context[key]

    members = frozenset(context.get("members") or ())
    items = [
        _safely("lookahead", lambda: check_lookahead(need("sources"))),
        _safely("universe", lambda: check_universe(need("facts"), context.get("membership"))),
        _safely("execution", lambda: check_execution(need("journal"), context.get("flags") or {})),
        _safely("costs", lambda: check_costs(
            need("journal"), context.get("schemes"), context.get("policy"),
            context.get("caller_commission"), context.get("routes"), members,
        )),
    ]
    return {
        "computedBy": "harness",
        "toolboxVersion": toolbox_version(),
        "computedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "items": items,
    }


def unavailable(reason: str) -> dict:
    """The block when assembling it failed: every check a ``warn`` with the reason."""
    return {
        "computedBy": "harness",
        "toolboxVersion": toolbox_version(),
        "computedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "items": [
            _item(check_id, "warn", f"checks could not run — {reason}"[:200], {"error": reason[:1000]})
            for check_id in CHECK_IDS
        ],
    }


def summary_line(checks: dict, seconds: float | None = None) -> str:
    parts = [f"{item['id']} {item['status']}" for item in checks.get("items", [])]
    tail = f" ({seconds * 1000:.0f} ms)" if seconds is not None else ""
    return "Checks: " + ", ".join(parts) + tail
