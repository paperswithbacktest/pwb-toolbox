import bisect
import copy
import json
import os
import itertools
import sys
import time
import pandas as pd
import numpy as np
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds

from ..engine import load as _load_engine

bt = _load_engine()  # backtrader by default, Tradewind on request; see pwb_toolbox.engine
from . import checks as _checks
from . import lookahead as _lookahead
from .feeds import ArrayPandasData


def _apply_broker_kwargs(broker: bt.BrokerBase, kwargs: dict) -> None:
    """Translate `broker_kwargs` into the correct broker setters."""
    if not kwargs:  # nothing to do
        return

    commission_fields = {}
    # -- per-side commission rate ---------------------------------------
    comm = kwargs.pop("commission", None)
    if isinstance(comm, dict):  # user gave full dict
        commission_fields.update(comm)
    elif comm is not None:  # just the rate
        commission_fields["commission"] = comm
    # -- cash-rate / interest -------------------------------------------
    interest = kwargs.pop("interest", None)
    if interest is not None:
        commission_fields["interest"] = interest
    # -- finally push the scheme into the broker ------------------------
    if commission_fields:
        broker.setcommission(**commission_fields)  # <<< only call we need
    # -- slippage (still a direct broker method) ------------------------
    slippage = kwargs.pop("slippage_perc", None)
    if slippage is not None:
        broker.set_slippage_perc(slippage)
    if kwargs:
        raise ValueError(f"Unknown broker kwarg(s): {', '.join(kwargs)}")


def _apply_per_symbol_commissions(
    broker, symbols, start_date, enable_impact=False, feeds=None, end_date=None,
    active_years=None,
) -> None:
    """Charge each symbol its own spread, for the years actually being traded.

    Three things the previous versions got wrong, each measured:

    * **It averaged.** Every data feed is added under its own name, so
      backtrader can price them separately -- and a basket of mega caps was
      paying the average of a universe that included micro caps. Measured on
      the cost dataset, the spread runs from 12 bp on high-priced names to
      175 bp on low-priced ones, so the mean is wrong in both directions at
      once. (``np.mean(list(get_commissions(symbols).values()))``.)

    * **It ignored ``start_date``.** The argument was available here and never
      passed, so costs were always estimated from 2020 onward -- including for
      a backtest starting in 1990, across the 2001 decimalisation that moved
      spreads by an order of magnitude.

    * **Then it froze the start year.** Passing ``start_date`` fixed the
      staleness and introduced a worse failure: **5 802 published strategies
      start at ``1990-01-01``**, thirteen years before the table begins, so the
      lookup missed, every symbol fell through to Roll, and the measured
      dataset was never read at all. A 32-strategy validation came back with
      zero measured spreads. The rate now follows the **year of the bar** --
      ``feeds`` carries the data objects the scheme reads the date from.

    The source of every rate is printed, because a break-even that rests on a
    measurement, on an extrapolated vintage and on an estimate are not the same
    claim.

    ``active_years`` (``{symbol: {year, ...}}`` with a bar) stops a vintage from
    being bridged across a hole in the prices -- see ``get_cost_schedules``. A
    year without a bar is charged the floor, and how many symbols that touches
    is printed with the rest.
    """
    priced = list(feeds) if feeds else list(symbols)
    # Resolved from ``symbols``, not ``priced``: the suffix that says which
    # asset a name refers to only exists on the caller's list, and it is the
    # only thing separating the crypto BTC from the US-listed ETF of the same
    # ticker that sits in the cost table at 119.6 bp. But resolved from the
    # list *expanded* the way ``get_pricing`` expanded it: judged as written,
    # ``["sp500"]`` gave ``{"sp500"}`` and every member was charged the floor.
    measurable, currencies = pwb_bt.cost_classes(symbols)
    schedules, summary = pwb_bt.get_cost_schedules(
        priced,
        start_date=start_date,
        end_date=end_date,
        measurable=measurable,
        active_years=active_years,
        currencies=currencies,
    )
    lambdas = pwb_bt.load_lambda_params() if enable_impact else {}
    year = int(str(start_date)[:4])
    end_year = int(str(end_date)[:4]) if end_date is not None else year
    span_years = range(min(year, end_year), max(year, end_year) + 1)
    absent = sum(
        1
        for symbol in summary
        if active_years and symbol in active_years
        and any(y not in active_years[symbol] for y in span_years)
    )

    schemes = {}
    for symbol, cost in summary.items():
        schedule = schedules.get(symbol)
        paired = (
            {
                y: (hs, lambdas.get((symbol, y), 0.0) if enable_impact else 0.0)
                for y, hs in schedule.items()
            }
            if schedule
            else None
        )
        scheme = pwb_bt.SpreadImpactCommission(
            half_spread=cost.half_spread,
            lambda_bps=lambdas.get((symbol, cost.year or year), 0.0),
            schedule=paired,
            data=(feeds or {}).get(symbol),
        )
        # Where the rate came from (measured, extrapolated, roll, default):
        # what the ``costs`` check reads.
        scheme.pwb_cost = cost
        broker.addcommissioninfo(scheme, name=symbol)
        schemes[symbol] = scheme

    rates = [c.half_spread for c in summary.values()]
    sources: dict[str, int] = {}
    for cost in summary.values():
        sources[cost.source] = sources.get(cost.source, 0) + 1
    detail = ", ".join(f"{n} {k}" for k, n in sorted(sources.items()))
    if absent:
        detail += f"; {absent} with years without a bar, charged the floor there"
    span = f"{year}" if end_date is None else f"{year}-{str(end_date)[:4]}"
    print(
        f"Commissions: {len(rates)} symbols, {span}, "
        f"{np.median(rates) * 1e4:.1f} bp median at {year}, "
        f"{min(rates) * 1e4:.1f}-{max(rates) * 1e4:.1f} bp range ({detail})"
    )
    return schemes


# ``broker.setcommission``'s positional order, the same on both engines.
_SETCOMMISSION_ARGS = (
    "commission", "margin", "mult", "commtype", "percabs", "stocklike",
    "interest", "interest_long", "leverage", "automargin", "name",
)


def _strategy_commission_floor(broker, schemes: dict) -> dict:
    """Let a strategy's own ``broker.setcommission`` raise its fees, never lower them.

    The measured per-symbol schemes are registered by name before the strategy
    exists, and a named scheme always wins over the default one, so a
    strategy's ``self.broker.setcommission(commission=0.001)`` used to set a
    scheme nothing ever consulted: a 1 bp name was charged 0.10 on a 1 000
    fill where the strategy asked for 1.00. 67 published strategies call it.

    The rule (decided 2026-11-03): **a strategy pays the higher of the two.**

    * A percentage scheme (``commtype`` ``COMM_PERC``, or ``None`` with no
      ``margin``) becomes a floor on the rate: each name pays
      ``max(measured half-spread of the year, requested rate)`` on every fill.
      A request of 0, or below the measured spread, changes nothing.
    * A per-unit scheme (``COMM_FIXED``, or ``None`` with a ``margin``) is
      compared fill by fill: the fill pays ``max(spread cost, fee x |size|)``.
      Nothing else of that scheme is taken -- ``margin``, ``mult``,
      ``stocklike``, ``interest`` and ``leverage`` would turn a stock into a
      future and move the NAV through position accounting rather than through
      costs. They are listed under ``ignored`` instead.
    * ``name=None`` applies to every measured name, ``name=<symbol>`` to that
      one only; a name the harness did not price falls through to the engine.
      Each call replaces the previous one, as ``setcommission`` itself does.

    Returns the policy dict that ``run_report["commission_policy"]`` exports.
    """
    perc = getattr(bt.CommInfoBase, "COMM_PERC", 0)
    policy = {"mode": "measured", "calls": [], "floor_perc": 0.0, "floor_fixed": 0.0,
              "raised_symbols": 0, "symbols": len(schemes)}
    original = broker.setcommission

    def setcommission(*args, **kwargs):
        call = dict(zip(_SETCOMMISSION_ARGS, args))
        call.update(kwargs)
        name = call.get("name")
        targets = [schemes[name]] if name in schemes else (
            list(schemes.values()) if name is None else []
        )
        if name is None or not targets:
            # The default scheme, as the engine would set it: consulted only
            # by a feed the harness did not price.
            original(*args, **kwargs)
        if not targets:
            return
        commission = float(call.get("commission", 0.0) or 0.0)
        commtype = call.get("commtype")
        margin = call.get("margin")
        is_perc = commtype == perc if commtype is not None else margin is None
        if is_perc:
            rate = commission if call.get("percabs", True) else commission / 100.0
            kind, value = "perc", max(rate, 0.0)
        else:
            kind, value = "fixed", max(commission, 0.0)
        for scheme in targets:
            scheme.floor_perc = value if kind == "perc" else 0.0
            scheme.floor_fixed = value if kind == "fixed" else 0.0
        defaults = {"mult": 1.0, "stocklike": False, "interest": 0.0,
                    "interest_long": False, "leverage": 1.0, "automargin": False}
        ignored = sorted(
            k for k, v in call.items()
            if (k == "margin" and v is not None) or (k in defaults and v != defaults[k])
        )
        raised = sum(
            1 for sc in schemes.values()
            if (sc.floor_perc > 0 and sc.floor_perc > min(sc.measured_rates()))
            or sc.floor_fixed > 0
        )
        policy["calls"].append({"name": name, "kind": kind, "value": value,
                                "symbols": len(targets), "ignored": ignored})
        policy["floor_perc"] = max((sc.floor_perc for sc in schemes.values()), default=0.0)
        policy["floor_fixed"] = max((sc.floor_fixed for sc in schemes.values()), default=0.0)
        policy["raised_symbols"] = raised
        policy["mode"] = "higher_of_measured_and_strategy"

    broker.setcommission = setcommission
    return policy


# What a fundable book is allowed to ask for: its long exposure as a share of
# the NAV. The missing 1 % is the commission: a book at exactly 100 % has no
# cash left to pay for the trade that got it there, so backtrader refuses the
# order and the NAV stops moving. Short legs are not counted -- their sale
# credits the cash that funds them, so a dollar-neutral book at gross 2 is
# fundable as it stands, and capping the gross halved it (0.1.31-0.1.42).
MAX_LEVERAGE = 0.99
# The name it had in 0.1.31-0.1.42, when it bounded the gross.
TARGET_GROSS = MAX_LEVERAGE

# Fallback step, applied when scaling the over-exposed bars was not enough
# (orders refused for another reason: buys submitted before the sells that
# fund them, an overnight gap), and the number of times it may be applied
# before the run is given up on.
DELEVERAGE_STEP = 0.90
DELEVERAGE_MAX_STEPS = 5

# Share of orders a run may fail to fund before it counts as underfunded. An
# isolated rejection on a gap day is noise; a systematic one freezes the NAV.
MARGIN_TOLERANCE = 0.02
# Debit a run may show, as a share of the NAV of the same bar, before it
# counts as underfunded. A debit of a dollar used to re-run the whole backtest.
DEBIT_TOLERANCE = 0.01
# How targets above MAX_LEVERAGE are brought back under it: on the bars that
# ask for it ("bar"), or over the whole run by the peak ("uniform", which keeps
# the shape of a book whose leverage is the strategy -- managed volatility,
# betting-against-beta -- and divides its returns instead).
SCALINGS = ("bar", "uniform")
# Full calendar years of missing bars that split one ticker into two instruments.
ERA_GAP_YEARS = 3

# Refuse orders on a symbol before its first real bar, instead of letting the
# back-fill below sell a flat line. ``PWB_REFUSE_BEFORE_LISTING=0`` switches it off.
REFUSE_BEFORE_LISTING = True

# What happens to a name that leaves a point-in-time universe ("sp500",
# "liquid1000"); see ``run_strategy``. ``PWB_PIT_EXIT`` in the environment
# overrides the default for a whole campaign.
PIT_EXITS = ("hold", "liquidate", "freeze")
PIT_EXIT = "hold"


def _era_cuts(closes: pd.DataFrame, gap_years: int) -> dict:
    """``{symbol: (first bar kept, first bar on disk, earlier eras)}``.

    A hole is ``gap_years`` full calendar years with no bar, bars on both
    sides. Only symbols with at least one hole are returned, cut at the last
    one.
    """
    cuts = {}
    for symbol in closes.columns:
        dates = closes.index[closes[symbol].notna()]
        if len(dates) < 2:
            continue
        gaps = dates[1:] - dates[:-1]
        holes = [i for i, gap in enumerate(gaps) if gap.days >= 365 * gap_years + 1]
        if holes:
            cuts[symbol] = (dates[holes[-1] + 1], dates[0], len(holes))
    return cuts


class FillAudit(bt.Analyzer):
    """Count the bars a position is held in a year where the symbol has no bar.

    ``run_strategy`` forward- and back-fills the price panel so every feed is
    aligned, which is right for holidays and wrong for a hole of several years:
    a ticker that changed hands (``BTC``: a micro cap to 2013, a listing in
    2021, an ETF since 2024) is then held on a flat series through 2014-2020
    and charged a spread at every rebalance. The cost side is handled by
    ``active_years``; this analyzer is the measurement of the other half -- how
    much of the book sat in an instrument that did not exist. It changes
    nothing; it says whether the fill should.

    ``inactive`` -- ``{symbol: {year, ...}}`` without a single bar.
    """

    params = (("inactive", None),)

    def start(self):
        self.held = {}

    def next(self):
        inactive = self.p.inactive or {}
        for data in self.datas:
            years = inactive.get(data._name)
            if not years:
                continue
            year = data.datetime.date(0).year
            if year not in years:
                continue
            if self.strategy.getposition(data).size:
                entry = self.held.setdefault(data._name, {"bars": 0, "years": set()})
                entry["bars"] += 1
                entry["years"].add(year)

    def get_analysis(self):
        return {
            symbol: {"bars": entry["bars"], "years": sorted(entry["years"])}
            for symbol, entry in sorted(self.held.items())
        }


class FundingAudit(bt.Analyzer):
    """Record every way a run outgrew the account it was given.

    Three symptoms of one cause -- the book asks for more than the account
    holds -- and all three are cured by asking for less:

    * ``margin``   -- orders backtrader refused outright, because funding them
      would have taken cash that the position being opened had just consumed.
      This is the one that freezes a NAV and publishes as a Sharpe of zero.
    * ``min_cash``  -- the low-water mark of the balance where the broker funds
      the order anyway and lets the account run a debit.
    * ``min_cash_ratio`` -- the same low-water mark as a share of that bar's
      NAV, which is what ``DEBIT_TOLERANCE`` is read against.
    * ``min_value`` -- the low-water mark of the NAV itself. A geared book that
      loses enough does not merely draw down, it goes through zero.
    """

    def start(self):
        self.margin = 0
        self.submitted = 0
        self.min_cash = None
        self.min_cash_ratio = None
        self.min_value = None

    def notify_order(self, order):
        if order.status == order.Submitted:
            self.submitted += 1
        elif order.status == order.Margin:
            self.margin += 1

    def next(self):
        broker = self.strategy.broker
        cash = broker.get_cash()
        marked = float(getattr(self.strategy, "_pwb_ms_marked", 0.0) or 0.0)
        if getattr(self.strategy, "_pwb_ms_added", False):
            # pit_exit="hold": the cash the harness books to mark a non-member
            # to its real close is value, not money -- a held name that fell
            # after its exit would read as a debit -- and a settlement booked
            # this bar is money the broker has not applied yet. All of it is
            # counted once everything asked for has landed -- also on a bar
            # where no mark is left but the reversal of the last one has not.
            cash = cash + _pending_cash(broker) - marked
        if self.min_cash is None or cash < self.min_cash:
            self.min_cash = cash
        value = self.strategy.broker.getvalue()
        if self.min_value is None or value < self.min_value:
            self.min_value = value
        if value > 0:
            ratio = cash / value
            if self.min_cash_ratio is None or ratio < self.min_cash_ratio:
                self.min_cash_ratio = ratio

    def get_analysis(self):
        submitted = max(self.submitted, 1)
        return {
            "margin": self.margin,
            "submitted": self.submitted,
            "reject_rate": self.margin / submitted,
            "min_cash": self.min_cash,
            "min_cash_ratio": self.min_cash_ratio,
            "min_value": self.min_value,
        }


def _underfunded(audit: dict, tolerance: float, debit_tolerance: float = DEBIT_TOLERANCE) -> bool:
    """True when the run outgrew the account: refused, in debit, or wiped out.

    The margin check itself stays in force -- this only decides whether the
    same strategy is worth re-running smaller. A debit counts only beyond
    ``debit_tolerance`` of the NAV: one day a dollar short used to re-run the
    whole backtest at a fraction of its exposure.
    """
    if audit["reject_rate"] > tolerance:
        return True
    ratio = audit.get("min_cash_ratio")
    if ratio is None and audit.get("min_cash") is not None:
        ratio = -float("inf") if audit["min_cash"] < 0 else 0.0  # an audit without the ratio
    if ratio is not None and ratio < -debit_tolerance:
        return True
    return audit["min_value"] is not None and audit["min_value"] <= 0


def _refuse_before_listing(broker, first_bar: dict) -> dict:
    """Make ``broker`` reject any order dated before its symbol's first real bar.

    ``run_strategy`` back-fills the panel so every feed starts on the same day,
    which is what keeps backtrader's feeds aligned and is harmless for a
    holiday. For a symbol listed years after ``start_date`` it paints a flat
    line the strategy can buy: ``FillAudit`` found the crypto books holding
    XRP for 2 711 bars of 2014-2024 -- an ETF listed in 2024, read from
    ``Stocks-Daily-Price`` and extended backwards at a constant price. The
    position earns nothing, pays the floor spread at every rebalance, and
    dilutes the book: a 1/N allocation over ten ETFs of which four did not
    exist yet is a 60 % invested book reported as 100 %.

    The guard sits on the broker rather than in the strategy because the
    strategy is the published ``strategy.py``: orders reach the broker by
    ``buy``, ``sell``, ``order_target_*`` or ``close``, and this is the one
    place they all pass. A refused order is notified as ``Rejected``, which is
    what a real broker answers for an instrument that does not trade yet.
    After the first bar the guard does nothing: the flat tail after a symbol's
    last bar, and the holes between, are a different matter -- an instrument
    that stopped printing may still be held or sold. For a name a
    point-in-time universe brought in, the bars outside its membership are
    guarded by ``_refuse_outside_universe``.

    Returns the audit, filled as the run goes: ``{symbol: {"orders": n,
    "first": date, "last": date}}`` of the refusals.
    """
    audit = {}
    original = broker.submit

    def submit(order, check=True):
        data = order.data
        listed = first_bar.get(getattr(data, "_name", None))
        if listed is not None:
            today = data.datetime.date(0)
            if today < listed.date():
                entry = audit.setdefault(
                    data._name, {"orders": 0, "first": today, "last": today}
                )
                entry["orders"] += 1
                entry["last"] = today
                order.reject(broker)
                broker.notify(order)
                return order
        return original(order, check=check)

    broker.submit = submit
    return audit


class _Membership:
    """The bars on which a point-in-time name is outside its universe.

    ``out`` -- ``{symbol: bool array over the trading days}``, only for the
    names that have at least one such bar, and only after their first real
    bar: before it ``_refuse_before_listing`` is the guard, as it always was.
    ``exits`` -- ``[(date, symbol)]`` sorted, the first bar of each absence.
    """

    def __init__(self, days: pd.DatetimeIndex, out: pd.DataFrame):
        self.day_index = {day.date(): i for i, day in enumerate(days)}
        self.names = set(out.columns)  # every name the universe brought in
        self.out = {}
        exits = []
        for symbol in out.columns:
            flags = out[symbol].to_numpy(dtype=bool)
            if not flags.any():
                continue
            self.out[symbol] = flags
            starts = np.flatnonzero(flags & ~np.r_[False, flags[:-1]])
            exits.extend((days[i].date(), symbol) for i in starts)
        self.exits = sorted(exits)

    def is_out(self, symbol, day) -> bool:
        flags = self.out.get(symbol)
        if flags is None:
            return False
        i = self.day_index.get(day)
        return i is not None and bool(flags[i])


def _pit_membership(symbols, present: pd.DataFrame, trading_days, cut: bool = True) -> "_Membership | None":
    """Where each name a point-in-time universe brought in sits outside it.

    ``present`` is the panel's row mask before any fill. A bar is outside when
    the name was not a member on that session *and* has no price row: the rows
    ``apply_pit_membership`` keeps (its as-of tolerance, a member's real bar)
    stay tradable, and so does a hole in a member's prices -- that one is a
    data gap, not an exit. Names the caller listed itself (``["sp500", "SPY"]``)
    are never cut, as in ``get_pricing``.

    ``cut=False`` is for a panel loaded with ``get_pricing(..., pit_cut=False)``,
    which kept every row: the rows the cut would have kept are then rebuilt from
    the membership with the same as-of tolerance, so the bars outside are the
    same as on a cut panel.
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    _, spec, added, explicit = pwb_ds._resolve_universe(list(symbols))
    if spec is None:
        return None
    names = [s for s in present.columns if s in added and s not in explicit]
    if not names:
        return None
    from pwb_toolbox.datasets.pit_universe import _ASOF_TOLERANCE, membership_mask

    member = membership_mask(trading_days, names, *spec).to_numpy()
    rows = present[names].reindex(trading_days, fill_value=False).to_numpy(dtype=bool)
    listed = np.maximum.accumulate(rows, axis=0)  # from the first real bar on
    if not cut:
        kept = membership_mask(trading_days, names, *spec, tolerance=_ASOF_TOLERANCE)
        rows = rows & kept.to_numpy()
    out = ~member & ~rows & listed
    return _Membership(trading_days, pd.DataFrame(out, index=trading_days, columns=names))


def _flatten_out_bars(pivot_df: pd.DataFrame, membership: "_Membership") -> None:
    """Make every bar outside the universe a flat bar at the last member close.

    The forward fill copies the whole last bar, its open included, so an order
    filled on the first bar outside would trade at a price already a day old.
    A flat bar at the last close is the price the liquidation gets, and it
    earns nothing while the name is away.
    """
    have = set(pivot_df.columns.get_level_values(0))
    names = [s for s in membership.out if s in have]
    if not names:
        return
    mask = np.column_stack([membership.out[s] for s in names])
    close = pivot_df[[(s, "close") for s in names]].to_numpy()
    for field in ("open", "high", "low"):
        columns = [(s, field) for s in names]
        if any(c not in pivot_df.columns for c in columns):
            continue
        block = pivot_df[columns].to_numpy(copy=True)
        block[mask] = close[mask]
        pivot_df[columns] = block


def _real_outside_prices(pivot_df: pd.DataFrame, membership: "_Membership") -> dict:
    """``{symbol: (open, close)}`` -- the real prices, holes forward-filled, of
    every name that has bars outside its universe, read before they are blanked."""
    out = {}
    for symbol in membership.out:
        raw = pivot_df[symbol]
        close = raw["close"].ffill()
        # On a bar without a print -- after a delisting, in a hole -- the
        # price a sale gets is the last close, not the last open.
        opens = raw["open"].where(raw["close"].notna(), close).ffill()
        out[symbol] = (opens.to_numpy(dtype=float), close.to_numpy(dtype=float))
    return out


def _blank_out_bars(pivot_df: pd.DataFrame, membership: "_Membership") -> None:
    """Empty the bars outside the universe, so the fill makes them the cut panel's flat line."""
    names = list(membership.out)
    if not names:
        return
    mask = np.column_stack([membership.out[s] for s in names])
    for field in ("open", "high", "low", "close"):
        columns = [(s, field) for s in names]
        if any(c not in pivot_df.columns for c in columns):
            continue
        block = pivot_df[columns].to_numpy(copy=True)
        block[mask] = np.nan
        pivot_df[columns] = block


def _refuse_outside_universe(
    broker, membership: "_Membership", state: dict, policy: str = "liquidate"
) -> dict:
    """Make ``broker`` reject any order on a name outside its point-in-time universe.

    The bars outside are a flat line (``_flatten_out_bars``), with a volatility,
    a beta and a correlation of zero: a low-volatility or a minimum-variance
    sort picks them first. Accepting the order would hold a position that
    earns nothing while the name is away and then takes, in one bar, the whole
    move it made in the meantime (CIT on 2009-12-10, 0.7 to 29 dollars). A
    real broker answers ``Rejected`` for an instrument the account may not
    trade, and the strategy is notified the same way. The liquidation the
    harness itself places at the exit passes (``state["liquidating"]``).

    With ``policy="hold"`` a position may still be open on the bars outside
    (it is held to the strategy's next rebalance): an order that only
    *reduces* it -- a sale of part or all of a long, a cover of a short --
    passes, and is settled at the real price by the strategy wrapper; only an
    order that opens, adds to or flips a position is refused.

    Returns the audit, filled as the run goes: ``{symbol: {"orders": n,
    "first": date, "last": date}}``.
    """
    audit = {}
    original = broker.submit
    hold = policy == "hold"

    def submit(order, check=True):
        if not state.get("liquidating"):
            data = order.data
            symbol = getattr(data, "_name", None)
            today = data.datetime.date(0)
            if membership.is_out(symbol, today) and not (
                hold and _reduces(broker.getposition(data).size, _signed(order))
            ):
                entry = audit.setdefault(symbol, {"orders": 0, "first": today, "last": today})
                entry["orders"] += 1
                entry["last"] = today
                order.reject(broker)
                broker.notify(order)
                return order
        return original(order, check=check)

    broker.submit = submit
    return audit


def _signed(order) -> float:
    size = abs(order.size)
    return size if order.isbuy() else -size


def _cheat_on_close(broker) -> bool:
    """Whether market orders fill at the close of the bar they were placed on.

    backtrader keeps the flag in ``broker.p.coc``; Tradewind's ``set_coc``
    sets ``broker._coc`` and leaves the parameter as it was.
    """
    flag = getattr(broker, "_coc", None)
    if flag is None:
        flag = getattr(getattr(broker, "p", None), "coc", False)
    return bool(flag)


def _pending_cash(broker) -> float:
    """What ``add_cash`` has been asked for and not yet applied to the broker's cash.

    It lands at the end of the next broker cycle, or earlier when a position
    value is asked for one feed (the oracle's ``add_cash_timing``) -- a timing
    a strategy's ``order_target_value`` moves. backtrader queues the amounts in
    a deque, Tradewind sums them in a float, under the same name.
    """
    pending = getattr(broker, "_cash_addition", None)
    if not pending:
        return 0.0
    try:
        return float(sum(pending))
    except TypeError:
        return float(pending)


def _reduces(position: float, size: float) -> bool:
    """Whether an order of ``size`` brings ``position`` closer to flat without flipping it."""
    after = position + size
    return bool(position) and abs(after) < abs(position) and after * position >= 0


def _with_exposure_cap(
    strategy_cls, cap: float = 1.0, schedule=None, membership=None, guard=None,
    pit_exit="liquidate", real_prices=None,
):
    """Subclass ``strategy_cls`` to scale, and record, every target it asks for.

    Acts on the order, not on a ``leverage`` parameter, because declaring one
    does not mean honouring it: both strategies that went flat on the margin
    cliff declare ``leverage`` and then call ``order_target_percent`` with a
    literal 1.0, and 1 803 of the 5 831 published strategies declare no such
    parameter at all. Scaling the request is the only lever that always exists.

    A target of ``order_target_percent`` or ``order_target_value`` is sent at
    ``target x cap x schedule(bar)``; ``schedule`` is ``(days, scales)``, read
    as of the bar's date, and comes from a first run of the same strategy (see
    ``run_strategy``). Orders by size, ``buy``/``sell`` and ``close`` are not
    scaled -- there is no target in them to scale.

    What the book asked for is recorded at the end of each bar that set a
    target: the targets of that bar, plus what every other name holds once its
    open orders are filled, at the weight the strategy asked for (a holding
    sent at a scale below 1 is divided by it, so a scaled run measures the
    same book). ``requested_long`` and ``requested_gross`` are the peaks of
    that record; what the bar holds as sent, scaled targets included, is
    ``_pwb_cap_funded``. 0.1.31-0.1.42 kept a target per name that only
    another target could reset, so a name exited by ``close()``, by size or
    through a refused order stayed in the sum for good: 4.9 for a book that
    never held more than 0.98 (``tests/test_exposure_cap.py``).

    With ``membership``, a position in a name that leaves its point-in-time
    universe is closed on the first bar outside (filled at the last member
    close, see ``_flatten_out_bars``); ``guard`` is the flag that lets that one
    order past ``_refuse_outside_universe``. With ``pit_exit="hold"`` the
    position is kept until the strategy's next rebalancing bar, and closed
    then if the strategy did not close it itself (a rebalancing bar is one on
    which the strategy placed an order or called an ``order_target_*`` on a
    name the universe brought in, even one that left its book unchanged; an
    order on a hedge or benchmark the caller listed itself does not count).
    The harness's close goes first in the broker's queue, so the purchases it
    funds pass the margin check. The feed stays flat outside, so the
    position is marked to its real close through the cash, one bar late
    (``_pwb_accrue``), and every sale filled there is settled at the real
    price: the broker fills it at the flat price and the difference with
    ``real_prices`` is added to the cash (``membership_settled``). The mark
    is not money: ``FundingAudit`` reads the cash without it
    (``_pwb_ms_marked``), and the exposure records value such a holding at
    its real close.
    ``is_tradable`` and ``is_member`` answer ``False`` for the name while it is
    outside, so a screen written with them never selects it.

    The wrapper's own state lives under ``_pwb_*`` names. It used to be
    ``self._targets``, ``self._record`` and ``self._scaling``, set *after* the
    strategy's ``__init__`` had run: a strategy keeping its target book in
    ``self._targets`` found it replaced by an empty dict, one defining its own
    ``_record(...)`` had it called with the wrapper's two arguments, and 21 of
    the published strategies use one of those names. A subclass that is not
    the strategy's author must not pick the names its author would.
    """
    days, scales = schedule if schedule else ((), ())
    guard = guard if guard is not None else {}
    hold = membership is not None and pit_exit == "hold"

    class _Capped(strategy_cls):
        exposure_cap = cap

        def __init__(self, *args, **kwargs):
            self._pwb_cap_scaling = False
            self._pwb_cap_day = None
            self._pwb_cap_req = {}  # name -> (data, weight) asked on the current bar
            self._pwb_cap_live = {}  # name -> data that may hold a position or an open order
            self._pwb_cap_orders = {}  # name -> orders not yet known to be dead
            self._pwb_cap_records = []  # (day, long, short) at the end of each bar with targets
            self._pwb_cap_applied = {}  # day -> scale below 1 sent with that bar's targets
            self._pwb_cap_sent = {}  # name -> scale sent with its latest order
            self._pwb_cap_funded = []  # (day, long) as sent: the bar's scaled targets + holdings
            self._pwb_ms_next = 0
            self._pwb_ms_watch = set()
            self._pwb_ms_filled = set()
            self._pwb_ms_orders = {}
            self._pwb_ms_feeds = None
            self._pwb_acted = None  # last bar on which the strategy placed or targeted anything
            self._pwb_ms_bar = None  # (len, date) of the bar is_member last looked at
            self.requested_gross = 0.0
            self.requested_long = 0.0
            self.membership_liquidations = {}
            self.membership_settled = {}  # name -> {"fills": n, "cash": added}
            self._pwb_ms_accrued = {}  # name -> cash booked to mark it to its real close
            self._pwb_ms_marked = 0.0  # their sum: in the broker's cash, not money (FundingAudit)
            self._pwb_ms_added = False  # the harness has called add_cash (FundingAudit)
            super().__init__(*args, **kwargs)

        # -- targets ----------------------------------------------------------
        def _pwb_feed(self, data):
            if data is None:
                return self.datas[0]
            if isinstance(data, str):
                return self.getdatabyname(data)
            return data

        def _pwb_cap_request(self, data, weight) -> float:
            try:
                day = data.datetime.date(0)
            except (IndexError, ValueError):  # an order placed before the first bar
                day = None
            if day != self._pwb_cap_day:
                self._pwb_cap_close_bar()
                self._pwb_cap_day = day
            name = getattr(data, "_name", None) or id(data)
            self._pwb_cap_req[name] = (data, float(weight))
            scale = cap
            if days and day is not None:
                i = bisect.bisect_right(days, day) - 1
                if i >= 0:
                    scale *= scales[i]
            self._pwb_cap_sent[name] = scale
            if scale < 1.0 and weight and day is not None:
                self._pwb_cap_applied[day] = min(scale, self._pwb_cap_applied.get(day, 1.0))
            return scale

        def _pwb_act(self, data=None):
            """Mark this bar as a rebalance when the order is on a name the universe brought in.

            An order on a name the caller listed itself -- a hedge, a
            benchmark, a cash proxy traded every day -- does not rebalance
            the book of members.
            """
            if not hold or not self.datas or guard.get("liquidating"):
                return
            try:
                data = self._pwb_feed(data)
            except (KeyError, IndexError):
                data = None
            if data is not None and getattr(data, "_name", None) not in membership.names:
                return
            try:
                self._pwb_acted = self.datas[0].datetime.date(0)
            except (IndexError, ValueError):
                pass

        def order_target_size(self, data=None, target=0, **kwargs):
            self._pwb_act(data)
            return super().order_target_size(data=data, target=target, **kwargs)

        def order_target_percent(self, data=None, target=0.0, **kwargs):
            self._pwb_act(data)
            # backtrader's own order_target_percent multiplies by the NAV and
            # calls order_target_value, which lands back here. Without the
            # guard the cap is applied twice -- 0.495 became 0.245 -- and the
            # recorded request is overwritten by the already-scaled figure.
            if self._pwb_cap_scaling:
                return super().order_target_percent(data=data, target=target, **kwargs)
            scale = self._pwb_cap_request(self._pwb_feed(data), target)
            self._pwb_cap_scaling = True
            try:
                return super().order_target_percent(data=data, target=target * scale, **kwargs)
            finally:
                self._pwb_cap_scaling = False

        def order_target_value(self, data=None, target=0.0, **kwargs):
            self._pwb_act(data)
            if self._pwb_cap_scaling:
                return super().order_target_value(data=data, target=target, **kwargs)
            value = self.broker.getvalue()
            scale = self._pwb_cap_request(
                self._pwb_feed(data), target / value if value else 0.0
            )
            self._pwb_cap_scaling = True
            try:
                return super().order_target_value(data=data, target=target * scale, **kwargs)
            finally:
                self._pwb_cap_scaling = False

        # -- every order, whatever sent it ----------------------------------------
        def buy(self, *args, **kwargs):
            self._pwb_act(kwargs.get("data", args[0] if args else None))
            return self._pwb_track(super().buy(*args, **kwargs))

        def sell(self, *args, **kwargs):
            self._pwb_act(kwargs.get("data", args[0] if args else None))
            return self._pwb_track(super().sell(*args, **kwargs))

        def _pwb_track(self, order):
            if order is not None:
                name = getattr(order.data, "_name", None) or id(order.data)
                self._pwb_cap_live[name] = order.data
                if not self._pwb_cap_scaling:  # by size or close(): nothing was scaled
                    self._pwb_cap_sent[name] = 1.0
                orders = [o for o in self._pwb_cap_orders.get(name, ()) if o.alive()]
                orders.append(order)
                self._pwb_cap_orders[name] = orders
            return order

        def _pwb_cap_held(self, name, data):
            """Shares held once the open orders fill, or None when nothing is left."""
            orders = [o for o in self._pwb_cap_orders.get(name, ()) if o.alive()]
            self._pwb_cap_orders[name] = orders
            size = self.getposition(data).size
            if not size and not orders:
                return None
            return size + sum(_signed(o) for o in orders)

        def _pwb_cap_close_bar(self):
            """Record what the bar's targets and every other holding add up to."""
            if not self._pwb_cap_req:
                return
            req, self._pwb_cap_req = self._pwb_cap_req, {}
            long = sum(w for _, w in req.values() if w > 0)
            short = -sum(w for _, w in req.values() if w < 0)
            sent = self._pwb_cap_sent
            funded = sum(w * sent.get(name, 1.0) for name, (_, w) in req.items() if w > 0)
            value = self.broker.getvalue()
            for name, data in list(self._pwb_cap_live.items()):
                held = self._pwb_cap_held(name, data)
                if held is None:
                    del self._pwb_cap_live[name]
                    self._pwb_cap_orders.pop(name, None)
                    continue
                if name in req or value <= 0:
                    continue
                weight = held * self._pwb_mark_price(name, data) / value
                if weight > 0:
                    funded += weight
                # In what the strategy asked for, not in what the cap let
                # through, so that a scaled run measures the same book.
                weight /= sent.get(name, 1.0)
                if weight > 0:
                    long += weight
                else:
                    short -= weight
            self._pwb_cap_records.append((self._pwb_cap_day, long, short))
            self._pwb_cap_funded.append((self._pwb_cap_day, funded))
            self.requested_long = max(self.requested_long, long)
            self.requested_gross = max(self.requested_gross, long + short)

        def _pwb_mark_price(self, name, data) -> float:
            """The close a holding is worth: the real one for a non-member held under "hold"."""
            price = float(data.close[0])
            if real_prices is not None and name in real_prices:
                i = membership.day_index.get(data.datetime.date(0))
                if i is not None and membership.out[name][i]:
                    real = real_prices[name][1][i]
                    if np.isfinite(real):
                        price = float(real)
            return price

        # -- names leaving the universe -----------------------------------------
        def _pwb_ms_step(self):
            day = self.datas[0].datetime.date(0)
            exits = membership.exits
            while self._pwb_ms_next < len(exits) and exits[self._pwb_ms_next][0] <= day:
                self._pwb_ms_watch.add(exits[self._pwb_ms_next][1])
                self._pwb_ms_next += 1
            if self._pwb_ms_filled:
                self._pwb_ms_watch |= self._pwb_ms_filled
                self._pwb_ms_filled = set()
            if not self._pwb_ms_watch:
                return
            if self._pwb_ms_feeds is None:
                self._pwb_ms_feeds = {getattr(d, "_name", None): d for d in self.datas}
            for name in sorted(self._pwb_ms_watch):
                data = self._pwb_ms_feeds.get(name)
                if data is None or not membership.is_out(name, day):
                    self._pwb_ms_watch.discard(name)
                    continue
                pending = self._pwb_ms_orders.get(name)
                if pending is not None and pending.alive():
                    continue
                if not self.getposition(data).size:
                    self._pwb_ms_watch.discard(name)
                    continue
                remaining = None
                if hold:
                    # Held at its real prices until the strategy rebalances.
                    if self._pwb_acted != day:
                        continue
                    # Net of what the strategy itself sent this bar (a sale
                    # outside passes the guard): close only what is left.
                    alive = [o for o in self._pwb_cap_orders.get(name, ()) if o.alive()]
                    remaining = self.getposition(data).size + sum(_signed(o) for o in alive)
                    if not remaining:
                        continue  # the strategy is closing it itself
                guard["liquidating"] = True
                try:
                    if remaining is None:
                        order = self.close(data)
                    elif remaining > 0:
                        order = self.sell(data, size=remaining)
                    else:
                        order = self.buy(data, size=-remaining)
                finally:
                    guard["liquidating"] = False
                if hold and order is not None:
                    # Placed after the strategy's own orders of the bar; put
                    # first, so that the margin check of the purchases it
                    # funds counts its proceeds (both engines check the
                    # submitted orders in turn, and the cash with them).
                    queue = getattr(self.broker, "submitted", None)
                    if queue is not None and queue and queue[-1] is order:
                        queue.pop()
                        queue.appendleft(order)
                self._pwb_ms_orders[name] = order
                entry = self.membership_liquidations.setdefault(
                    name, {"orders": 0, "first": day, "prices": []}
                )
                entry["orders"] += 1

        def _pwb_settle(self, order, name):
            """Pay a fill outside the universe at the real price instead of the flat one."""
            day = order.data.datetime.date(0)
            i = membership.day_index.get(day)
            if i is None:
                return
            opens, closes = real_prices[name]
            if order.exectype == order.Market and i > 0 and _cheat_on_close(self.broker):
                # cheat-on-close: filled at the close of the bar it was placed on
                i -= 1
                real = closes[i]
            elif order.exectype == order.Close:
                real = closes[i]
            else:
                real = opens[i]
            if not membership.out[name][i]:
                return  # the price it filled at was a real one
            size = float(order.executed.size)
            if not size or not np.isfinite(real):
                return
            cash = -size * (float(real) - float(order.executed.price))
            if cash:
                self.broker.add_cash(cash)
                self._pwb_ms_added = True
            entry = self.membership_settled.setdefault(name, {"fills": 0, "cash": 0.0})
            entry["fills"] += 1
            entry["cash"] += cash

        def notify_order(self, order):
            if membership is not None and order.status == order.Completed:
                name = getattr(order.data, "_name", None)
                if real_prices is not None and name in real_prices:
                    self._pwb_settle(order, name)
                if name in membership.out:
                    self._pwb_ms_filled.add(name)
                    mine = self._pwb_ms_orders.get(name)
                    if mine is not None and mine.ref == order.ref:
                        self.membership_liquidations[name]["prices"].append(
                            order.executed.price
                        )
            return super().notify_order(order)

        # -- what the strategy may select ---------------------------------------------
        def _pwb_is_out(self, data) -> bool:
            if membership is None or not self.datas:
                return False
            name = data if isinstance(data, str) else getattr(data, "_name", None)
            if name not in membership.out:
                return False
            bar = len(self)
            if self._pwb_ms_bar is None or self._pwb_ms_bar[0] != bar:
                # one date conversion per bar, not one per name a screen asks about
                self._pwb_ms_bar = (bar, self.datas[0].datetime.date(0))
            return membership.is_out(name, self._pwb_ms_bar[1])

        def is_member(self, data) -> bool:
            if self._pwb_is_out(data):
                return False
            parent = getattr(super(), "is_member", None)
            return parent(data) if parent is not None else True

        if hold:

            def is_tradable(self, data, *args, **kwargs):
                if self._pwb_is_out(data):
                    return False
                return super().is_tradable(data, *args, **kwargs)

        # -- end of each bar --------------------------------------------------------
        def _pwb_accrue(self):
            """Mark what is held outside the universe to its real close, through the cash.

            The feed is flat there, so the broker values the position at its
            last member close. The difference with the real close is booked as
            cash -- ``add_cash`` lands at the end of the next broker cycle, in
            both engines, so the mark lags one bar and the margin checks of
            the next bar see the cash the orders were sized on -- and reversed
            on the bar before the name comes back, when the feed itself jumps
            to the real price. A sale is
            settled on its own in ``_pwb_settle``. ``_pwb_ms_marked`` is the
            sum of these marks, landed or not (``FundingAudit``).
            """
            day = self.datas[0].datetime.date(0)
            i = membership.day_index.get(day)
            if i is None:
                return
            if self._pwb_ms_feeds is None:
                self._pwb_ms_feeds = {getattr(d, "_name", None): d for d in self.datas}
            for name in set(self._pwb_ms_accrued) | self._pwb_ms_watch:
                data = self._pwb_ms_feeds.get(name)
                if data is None or name not in real_prices:
                    continue
                flags = membership.out[name]
                target = 0.0
                if flags[i] and i + 1 < len(flags) and flags[i + 1]:
                    size = self.getposition(data).size
                    real = real_prices[name][1][i]
                    if size and np.isfinite(real):
                        target = size * (float(real) - float(data.close[0]))
                booked = self._pwb_ms_accrued.get(name, 0.0)
                if target != booked:
                    self.broker.add_cash(target - booked)
                    self._pwb_ms_added = True
                if target:
                    self._pwb_ms_accrued[name] = target
                else:
                    self._pwb_ms_accrued.pop(name, None)
            self._pwb_ms_marked = float(sum(self._pwb_ms_accrued.values()))

        def _pwb_after_bar(self):
            self._pwb_cap_close_bar()
            if membership is not None and self.datas:
                self._pwb_ms_step()
                if real_prices is not None:
                    self._pwb_accrue()

        def prenext(self):
            super().prenext()
            self._pwb_after_bar()

        def next(self):
            super().next()
            self._pwb_after_bar()

        def stop(self):
            self._pwb_cap_close_bar()
            return super().stop()

    _Capped.__name__ = f"{strategy_cls.__name__}Capped{round(cap * 100)}"
    _Capped.__qualname__ = _Capped.__name__
    return _Capped


def _bar_schedule(records, max_leverage: float):
    """``(days, scales)``: each bar's targets brought under ``max_leverage``.

    ``records`` is ``(day, long, short)`` per bar that set a target, from a run
    of the strategy as published. A bar that asked for more long exposure than
    the account funds is scaled to fit; every other bar is left at 1. 0.1.31-
    0.1.42 divided every bar by the peak of the whole run instead: a book
    levered to 200 % for a few weeks ran at a quarter of its targets for the
    other twenty years.
    """
    asked = {}
    for day, long, _ in records:
        asked[day] = max(asked.get(day, 0.0), long)
    days = sorted(asked)
    scales = [
        max_leverage / asked[d] if asked[d] > max_leverage else 1.0 for d in days
    ]
    return days, scales


def run_strategy(
    indicator_cls,
    indicator_kwargs,
    strategy_cls,
    strategy_kwargs,
    symbols,
    start_date,
    cash,
    cerebro_kwargs=None,
    broker_kwargs=None,
    enable_impact=False,
    deleverage=True,
    margin_tolerance=MARGIN_TOLERANCE,
    era_gap_years=None,
    refuse_before_listing=None,
    max_leverage=MAX_LEVERAGE,
    scaling="bar",
    debit_tolerance=DEBIT_TOLERANCE,
    pit_exit=None,
):
    """Run a tactical asset allocation strategy with Backtrader.

    ``era_gap_years`` -- a symbol whose price series has a hole of at least
    that many full calendar years keeps only what follows its **last** such
    hole. Default ``ERA_GAP_YEARS`` (3); ``0`` keeps every bar on disk. A
    ticker is the only identity the price panel has and tickers get reused:
    ``BTC`` is a 2003-2013 micro cap, a 2021 listing and the Grayscale ETF
    since July 2024, and the forward-fill below stitches them
    into one series with a +1 000 % day and a −90 % day at the seams. The
    instrument the strategy names is the one trading today, so the earlier
    eras are dropped (the leading back-fill then makes them a flat line, which
    the cost schedule charges at the floor and ``FillAudit`` reports). It is
    the default since 0.1.36: measured on/off on the 80 published strategies
    most exposed to ticker reuse, 10 received a cut, 7 of them moved by less
    than the sampling noise of a Sharpe, 2 gained and the 1 that lost had
    earned its Sharpe on another instrument's bars. ``PWB_ERA_GAP_YEARS`` in
    the environment overrides it for a whole campaign without touching the
    strategies (``PWB_ERA_GAP_YEARS=0`` switches it off).

    ``refuse_before_listing`` -- the broker rejects any order on a symbol dated
    before that symbol's first real bar (default ``REFUSE_BEFORE_LISTING``,
    ``PWB_REFUSE_BEFORE_LISTING=0`` in the environment switches it off). The
    panel is back-filled so every feed starts on the same day, which paints a
    flat line in front of a symbol listed after ``start_date``; a strategy
    that buys it holds a position earning nothing, pays the floor spread at
    each rebalance and reports a 1/N book as fully invested when part of it
    did not exist. See ``_refuse_before_listing``; the refusals are on the
    returned strategy as ``listing_audit``.

    **Point-in-time universes** (``"sp500"``, ``"liquid1000"``). ``pit_exit``
    (default ``PIT_EXIT``, ``PWB_PIT_EXIT`` in the environment) says what
    happens to a name that leaves the universe:

    * ``"hold"`` (the default) -- what the papers do: a book formed among the
      members is held to the next rebalance and earns the names' **real**
      returns, whether they stay in the universe or not. An order that opens,
      adds to or flips a position in a non-member is refused, a sale passes;
      whatever the strategy still holds in a non-member on its next
      rebalancing bar (any bar on which it calls an order method on a name
      the universe brought in -- not on a hedge it listed itself) is closed
      by the harness, its order checked before the strategy's own. The feed is the same flat line as with ``"liquidate"``
      -- screens that skip flat lines keep working --; a non-member still held
      is marked to its real close through the cash (one bar late: the
      broker has marked the bar before the strategy runs), and a sale filled
      outside is settled at the real price. The funding audit reads the cash
      without those marks. ``is_tradable`` and ``is_member`` answer ``False``
      for a non-member. The panel is loaded uncut
      (``get_pricing(pit_cut=False)``) and blanked here, so the era cut reads
      the real holes: a name out of the universe for three years keeps its
      earlier membership (on the cut panel that hole looked like a reused
      ticker, and everything before it was dropped).
    * ``"liquidate"`` (0.1.43) -- the panel is cut to the membership, the bars
      outside are flat at the last member close, a position is closed on the
      first of them at that price, and any other order on the name is refused
      (``Rejected``) until it is a member again.
    * ``"freeze"`` (0.1.42 and before) -- cut panel, forward fill, nothing
      sold or refused: a non-member is a flat line that can be bought and held,
      and the move it made while away lands in one bar at its return. Kept to
      reproduce a past measure.

    A hole in the prices of a *member* is forward-filled in every mode. The
    refusals and closes are on the returned strategy as ``membership_audit``.

    **Funding.** The run is first made as published. If it outgrew the account
    -- more than ``margin_tolerance`` of its orders refused for margin, a debit
    beyond ``debit_tolerance`` of the NAV, or the NAV through zero -- and
    ``deleverage`` is on, it is run again with each target of
    ``order_target_percent``/``order_target_value`` scaled on the bars that
    asked for more long exposure than ``max_leverage`` (default 0.99: a 100 %
    book plus its commission is refused by backtrader, at 99 % it trades).
    Short legs do not count, their proceeds fund them. With
    ``scaling="uniform"`` the whole run is divided by its peak instead, which
    keeps the shape of a book whose time-varying leverage *is* the strategy
    (returns, volatility and drawdowns shrink by that factor, the Sharpe ratio
    does not). Orders by size, ``buy``/``sell`` and ``close`` are never scaled,
    so a book without a target is not re-run at all. If the scaled run is still
    underfunded, the targets are stepped down by ``DELEVERAGE_STEP`` up to
    ``DELEVERAGE_MAX_STEPS`` times; if nothing works the run as published is
    returned. A bar schedule that one step did not fund, and whose run held
    more than ``max_leverage`` on over ``margin_tolerance`` of its bars with
    positions an earlier bar had sized, is replaced by one scale for the whole
    run (0.99 over the peak, ``run_report["scaling_used"] == "uniform"``): a
    book that keeps positions across bars without re-targeting them -- daily
    cohorts held two days -- carries each one at the scale of the bar that
    sent it, which no schedule of the next bars can correct. At one scale, a
    step goes straight to 0.99 over the peak that run measured when it is
    lower than the step. ``max_leverage`` cannot exceed 1: backtrader refuses at execution
    any buy the cash does not cover, ``checksubmit`` or not, so leverage above
    the account is not something the harness can fund.

    The returned strategy carries ``exposure_cap`` (the smallest scale sent
    with any target, 1.0 when none was scaled), ``requested_long`` and
    ``requested_gross`` (the peaks of what the book asked for, as published),
    ``funding_audit`` and ``run_report`` (all of it, plus the number of runs
    and of scaled bars); the same summary is printed on one ``Exposure:`` line.
    A run that stays underfunded is returned with ``run_report["underfunded"]``
    set, so the caller can refuse it rather than record a number.
    """
    if not 0 < max_leverage <= 1:
        raise ValueError(
            f"max_leverage={max_leverage}: it must be in (0, 1]. backtrader refuses "
            "at execution any buy the cash does not cover, so a book levered "
            "above its account cannot be funded; use scaling='uniform' to keep "
            "the shape of a levered book at a fundable level."
        )
    if scaling not in SCALINGS:
        raise ValueError(f"scaling={scaling!r}: one of {SCALINGS}")
    if pit_exit is None:
        pit_exit = os.getenv("PWB_PIT_EXIT", PIT_EXIT) or PIT_EXIT
    if pit_exit not in PIT_EXITS:
        raise ValueError(f"pit_exit={pit_exit!r}: one of {PIT_EXITS}")
    # The automatic checks (``checks.py``): the strategy's code is read now,
    # while the frames that hold it -- a file, a notebook cell, the caller of
    # ``exec`` -- are still on the stack. Nothing here may stop the run.
    checking = _checks.enabled()
    check_context = {}
    check_seconds = 0.0
    if checking:
        started = time.perf_counter()
        try:
            check_context["sources"] = _lookahead.strategy_source(
                strategy_cls, indicator_cls, sys._getframe(1)
            )
        except Exception as exc:  # noqa: BLE001
            check_context["sources_error"] = f"{type(exc).__name__}: {exc}"
        check_seconds += time.perf_counter() - started
    # The default observers (Broker, BuySell, Trades) exist for plotting and
    # cost about a tenth of the engine loop; nothing in the harness or in the
    # published strategies reads them, and the dozen strategies that build
    # their own Cerebro already pass ``stdstats=False``. A caller who plots
    # passes ``cerebro_kwargs={"stdstats": True}``.
    cerebro_kwargs = {"stdstats": False, **(cerebro_kwargs or {})}
    broker_kwargs = broker_kwargs or {}
    # Load the data from https://paperswithbacktest.com/datasets -- once, and
    # reused across attempts, because a re-run must not re-download anything.
    pivot_df = pwb_ds.get_pricing(
        symbol_list=symbols,
        fields=["open", "high", "low", "close"],
        start_date=start_date,
        extend=True,  # Extend the dataset with proxy data
        # "hold" values a position carried through an exit at its real
        # prices, so it needs the rows the membership cut would drop.
        pit_cut=pit_exit != "hold",
    )
    # Which feed each column came from (``get_pricing``), popped so pandas
    # does not carry it through every operation below.
    routes = dict(pivot_df.attrs.pop("pwb_routes", None) or {})
    # Which years each symbol actually has a bar in, read before the fill
    # below erases the holes. The cost schedule charges the floor in a year
    # without a bar instead of bridging a vintage across it, and ``FillAudit``
    # counts what the strategy holds there. Both exist because a ticker is the
    # only identity the price panel has, and tickers get reused.
    closes = (
        pivot_df.xs("close", axis=1, level=1)
        if isinstance(pivot_df.columns, pd.MultiIndex)
        else pivot_df
    )
    if era_gap_years is None:
        era_gap_years = int(os.getenv("PWB_ERA_GAP_YEARS", ERA_GAP_YEARS))
    if era_gap_years:
        cuts = _era_cuts(closes, era_gap_years)
        for symbol, (cut, dropped_from, eras) in cuts.items():
            pivot_df.loc[pivot_df.index < cut, symbol] = np.nan
            closes.loc[closes.index < cut, symbol] = np.nan
            print(
                f"Era cut: {symbol} keeps bars from {cut.date()}, dropped "
                f"{dropped_from.date()} to the last hole ({eras} earlier instrument"
                f"{'s' if eras > 1 else ''} under the ticker)"
            )
    present = closes.notna()
    if checking:
        started = time.perf_counter()
        try:
            check_context["facts"] = _checks.universe_facts(symbols, present, routes)
            _, _, added, explicit = pwb_ds._resolve_universe(
                [symbols] if isinstance(symbols, str) else list(symbols)
            )
            check_context["members"] = frozenset(added) - frozenset(explicit)
        except Exception as exc:  # noqa: BLE001
            check_context["facts_error"] = f"{type(exc).__name__}: {exc}"
        check_context["routes"] = routes
        check_seconds += time.perf_counter() - started
    active_years = {
        symbol: set(present.index[present[symbol]].year) for symbol in present.columns
    }
    # The first real bar of each symbol, read before the back-fill below
    # paints a flat line in front of it; what ``_refuse_before_listing`` guards.
    first_bar = {
        symbol: present.index[present[symbol]].min()
        for symbol in present.columns
        if present[symbol].any()
    }
    if refuse_before_listing is None:
        refuse_before_listing = os.getenv(
            "PWB_REFUSE_BEFORE_LISTING", "1" if REFUSE_BEFORE_LISTING else "0"
        ) != "0"
    # Create trading-day index (optional but keeps Cerebro happy)
    trading_days = pd.bdate_range(pivot_df.index.min(), pivot_df.index.max())
    membership = _pit_membership(symbols, present, trading_days, cut=pit_exit != "hold")
    pivot_df = pivot_df.reindex(trading_days)
    real_prices = None
    if pit_exit == "hold" and membership is not None:
        # The feed the strategy reads is the one "liquidate" builds -- flat
        # outside the universe, so a screen that skips flat lines (439 of the
        # published "sp500" strategies) still never sees a non-member move.
        # The real prices of those bars are kept aside to settle the sales.
        real_prices = _real_outside_prices(pivot_df, membership)
        _blank_out_bars(pivot_df, membership)
        # A name whose rows all lie outside its membership has no column on
        # the cut panel; blanked, it would be a feed of NaN.
        empty = [
            s for s in membership.out
            if s in pivot_df.columns.get_level_values(0) and pivot_df[(s, "close")].isna().all()
        ]
        if empty:
            pivot_df = pivot_df.drop(columns=empty, level=0)
            pivot_df.columns = pivot_df.columns.remove_unused_levels()
    pivot_df.ffill(inplace=True)  # forward-fill holidays
    pivot_df.bfill(inplace=True)  # back-fill leading IPO gaps
    all_years = set(trading_days.year)
    inactive = {
        symbol: all_years - years for symbol, years in active_years.items()
        if all_years - years
    }
    if pit_exit in ("liquidate", "hold") and membership is not None:
        _flatten_out_bars(pivot_df, membership)
    # "freeze" is 0.1.42: the bars outside are the forward fill, nothing is
    # sold or refused. Kept to reproduce a past measure, not to publish one.
    acting = membership if pit_exit != "freeze" else None

    def attempt(cap, schedule):
        # Engine configuration
        cerebro = bt.Cerebro(**cerebro_kwargs)
        # Keyed by feed name, because that is what ``addcommissioninfo(name=...)``
        # matches on, and what the scheme reads the bar date from.
        feeds = {}
        for symbol in pivot_df.columns.levels[0]:
            data = ArrayPandasData(dataname=pivot_df[symbol].copy())
            cerebro.adddata(data, name=symbol)
            feeds[symbol] = data
        guard = {"liquidating": False}
        # Strategy
        cerebro.addstrategy(
            _with_exposure_cap(
                strategy_cls, cap, schedule=schedule, membership=acting, guard=guard,
                pit_exit=pit_exit, real_prices=real_prices,
            ),
            total_days=len(trading_days),
            indicator_cls=indicator_cls,
            indicator_kwargs=indicator_kwargs,
            **strategy_kwargs,
        )
        cerebro.addanalyzer(FundingAudit, _name="funding")
        cerebro.addanalyzer(FillAudit, _name="fill", inactive=inactive)
        created = {}
        if checking:
            cerebro.addanalyzer(_checks.OrderJournal, _name="pwb_journal", created=created)
        # Broker. ``_apply_broker_kwargs`` pops what it consumes, so each
        # attempt gets its own copy -- otherwise the second run of a
        # de-leveraging sequence would silently lose the caller's commission
        # and fall back to the measured per-symbol scheme.
        run_broker_kwargs = copy.deepcopy(broker_kwargs)
        cerebro.broker.set_cash(cash)
        if "commission" not in run_broker_kwargs:
            schemes = _apply_per_symbol_commissions(
                cerebro.broker,
                symbols,
                start_date,
                enable_impact=enable_impact,
                feeds=feeds,
                end_date=pivot_df.index.max(),
                active_years=active_years,
            )
        else:
            schemes = None
        _apply_broker_kwargs(cerebro.broker, run_broker_kwargs)
        # After the caller's kwargs, so only the strategy's own calls are seen.
        commission_policy = (
            _strategy_commission_floor(cerebro.broker, schemes)
            if schemes
            else {"mode": "caller", "commission": broker_kwargs.get("commission")}
        )
        if checking:
            # Innermost: it sees the orders the guards below let through.
            _checks.record_submissions(cerebro.broker, created)
        # Inner guard first: an order dated before the listing is refused by
        # the listing guard and counted there, as before the membership one.
        refused_outside = (
            _refuse_outside_universe(cerebro.broker, acting, guard, pit_exit)
            if acting is not None
            else {}
        )
        listing_audit = (
            _refuse_before_listing(cerebro.broker, first_bar)
            if refuse_before_listing
            else {}
        )
        # Run the strategy
        strategy = cerebro.run()[0]
        strategy.commission_policy = commission_policy
        strategy.cost_schemes = schemes
        if checking:
            try:
                strategy.order_journal = strategy.analyzers.pwb_journal.get_analysis()
                strategy.broker_flags = _checks.broker_flags(cerebro.broker)
            except Exception as exc:  # noqa: BLE001
                strategy.order_journal = None
                strategy.order_journal_error = f"{type(exc).__name__}: {exc}"
        strategy.listing_audit = listing_audit
        if listing_audit:
            worst = max(listing_audit.items(), key=lambda kv: kv[1]["orders"])
            refused = sum(entry["orders"] for entry in listing_audit.values())
            print(
                f"Refused before listing: {refused} orders on {len(listing_audit)} "
                f"symbols, e.g. {worst[0]} {worst[1]['first']} to {worst[1]['last']} "
                f"(first bar {first_bar[worst[0]].date()})"
            )
        strategy.pit_exit = pit_exit
        strategy.pit_membership = membership
        strategy.membership_audit = {
            "refused": refused_outside,
            "liquidated": strategy.membership_liquidations,
            "settled": strategy.membership_settled,
        }
        if refused_outside or strategy.membership_liquidations:
            refused = sum(entry["orders"] for entry in refused_outside.values())
            print(
                f"Out of universe: {refused} orders refused on {len(refused_outside)} "
                f"symbols, {len(strategy.membership_liquidations)} positions closed "
                + (
                    "at the next rebalance" if pit_exit == "hold"
                    else "at their last member price"
                )
            )
        audit = strategy.analyzers.funding.get_analysis()
        audit["requested_gross"] = strategy.requested_gross
        audit["requested_long"] = strategy.requested_long
        strategy.funding_audit = audit
        strategy.fill_audit = strategy.analyzers.fill.get_analysis()
        if strategy.fill_audit:
            worst = max(strategy.fill_audit.items(), key=lambda kv: kv[1]["bars"])
            print(
                f"Held while absent: {len(strategy.fill_audit)} symbols with a position "
                f"in a year without a bar, e.g. {worst[0]} {worst[1]['years'][0]}-"
                f"{worst[1]['years'][-1]} ({worst[1]['bars']} bars)"
            )
        return strategy

    def finish(strategy, as_published, attempts, cap, underfunded):
        applied = list(strategy._pwb_cap_applied.values())
        scaled = [s for s in applied if s < 1.0]
        report = {
            "attempts": attempts,
            "scaling": scaling,
            "scaling_used": "uniform" if fallback else scaling,
            "max_leverage": max_leverage,
            "exposure_cap": min([cap] + applied),
            "step_cap": cap,
            "requested_long": as_published.requested_long,
            "requested_gross": as_published.requested_gross,
            "target_bars": len({r[0] for r in strategy._pwb_cap_records}),
            "scaled_bars": len(scaled),
            "median_scale": float(np.median(scaled)) if scaled else 1.0,
            "underfunded": bool(underfunded),
            "funding": dict(strategy.funding_audit),
            "funding_as_published": (
                dict(as_published.funding_audit) if as_published is not strategy else None
            ),
            "commission_policy": getattr(strategy, "commission_policy", None),
            "membership": {
                "pit_exit": pit_exit,
                "refused_orders": sum(
                    e["orders"] for e in strategy.membership_audit["refused"].values()
                ),
                "refused_symbols": len(strategy.membership_audit["refused"]),
                "liquidated_symbols": len(strategy.membership_audit["liquidated"]),
                "settled_fills": sum(
                    e["fills"] for e in strategy.membership_audit["settled"].values()
                ),
                "settled_cash": float(sum(
                    e["cash"] for e in strategy.membership_audit["settled"].values()
                )),
            },
        }
        strategy.exposure_cap = report["exposure_cap"]
        strategy.requested_long = as_published.requested_long
        strategy.requested_gross = as_published.requested_gross
        if checking:
            started = time.perf_counter()
            context = dict(check_context)
            context.update(
                membership=membership,
                journal=getattr(strategy, "order_journal", None),
                flags=getattr(strategy, "broker_flags", None),
                schemes=getattr(strategy, "cost_schemes", None),
                policy=report["commission_policy"],
                caller_commission=broker_kwargs.get("commission"),
            )
            if getattr(strategy, "order_journal_error", None):
                context["journal_error"] = strategy.order_journal_error
            try:
                report["checks"] = _checks.compute(context)
            except Exception as exc:  # noqa: BLE001 -- compute() should not raise
                report["checks"] = _checks.unavailable(f"{type(exc).__name__}: {exc}")
            strategy.checks = report["checks"]
            print(_checks.summary_line(
                report["checks"], check_seconds + time.perf_counter() - started
            ))
        strategy.run_report = report
        policy = report["commission_policy"] or {}
        if policy.get("calls"):
            print("Commission policy: " + json.dumps({
                "mode": policy["mode"],
                "floor_perc": policy["floor_perc"],
                "floor_fixed": policy["floor_fixed"],
                "raised_symbols": policy["raised_symbols"],
                "symbols": policy["symbols"],
                "calls": len(policy["calls"]),
                "ignored": sorted({k for c in policy["calls"] for k in c["ignored"]}),
            }))
        funding = strategy.funding_audit
        print("Exposure: " + json.dumps({
            "exposure_cap": round(report["exposure_cap"], 6),
            "scaled_bars": report["scaled_bars"],
            "target_bars": report["target_bars"],
            "median_scale": round(report["median_scale"], 6),
            "requested_long": round(report["requested_long"], 6),
            "requested_gross": round(report["requested_gross"], 6),
            "attempts": attempts,
            "scaling": scaling,
            "scaling_used": report["scaling_used"],
            "reject_rate": round(funding["reject_rate"], 6),
            "min_cash_ratio": (
                None if funding["min_cash_ratio"] is None
                else round(funding["min_cash_ratio"], 6)
            ),
            "underfunded": bool(underfunded),
        }))
        return strategy

    cap, schedule, steps, attempts, as_published = 1.0, None, 0, 0, None
    fallback = False
    while True:
        strategy = attempt(cap, schedule)
        attempts += 1
        if as_published is None:
            as_published = strategy
        audit = strategy.funding_audit
        underfunded = _underfunded(audit, margin_tolerance, debit_tolerance)
        if not underfunded or not deleverage:
            return finish(strategy, as_published, attempts, cap, underfunded)

        why = (
            f"{audit['margin']}/{audit['submitted']} orders refused for margin"
            + (
                f", min cash {audit['min_cash']:,.0f} ({audit['min_cash_ratio']:.2%} of NAV)"
                if audit["min_cash_ratio"] is not None
                and audit["min_cash_ratio"] < -debit_tolerance
                else ""
            )
            + (
                f", NAV through zero ({audit['min_value']:,.0f})"
                if audit["min_value"] is not None and audit["min_value"] <= 0
                else ""
            )
        )
        if attempts == 1:
            if not as_published._pwb_cap_records:
                # Nothing set a target, so there is nothing a re-run could
                # scale: 0.1.31-0.1.42 re-ran such a book five more times.
                print(f"Underfunded as published: {why} -- no target to scale, not re-run")
                return finish(strategy, as_published, attempts, cap, underfunded)
            peak = as_published.requested_long
            if peak > max_leverage:
                if scaling == "uniform":
                    cap = max_leverage / peak
                    print(
                        f"Underfunded as published: {why} -- re-running every target "
                        f"at {cap:.1%} (the book peaks at {peak:.0%} long)"
                    )
                else:
                    schedule = _bar_schedule(as_published._pwb_cap_records, max_leverage)
                    over = sum(1 for s in schedule[1] if s < 1.0)
                    print(
                        f"Underfunded as published: {why} -- re-running with the "
                        f"{over} of {len(schedule[0])} target bars above "
                        f"{max_leverage:.0%} long scaled to it (peak {peak:.0%})"
                    )
                continue
        if schedule is not None and steps:
            # Bar scaling sizes the targets of a bar against what that bar
            # asks for, and leaves every name it does not re-target at the
            # scale of the bar that sent it. A book that holds positions
            # across bars -- a cohort entered every day and held two, a
            # rotation of part of the book -- carries a position sized at
            # 99 % into a bar whose own targets are scaled for 200 %: the
            # account is over whatever that bar's scale, and stepping the
            # schedule down shrinks every bar without curing it (0.1.43:
            # five steps, 59 % of a schedule whose refusals then changed
            # the path). One scale for the whole run fits such a book.
            over = max_leverage + debit_tolerance
            funded = strategy._pwb_cap_funded
            carried = sum(1 for _, long in funded if long > over)
            if carried > margin_tolerance * max(len(funded), 1):
                peak = as_published.requested_long
                schedule, cap, fallback = None, max_leverage / peak, True
                print(
                    f"Underfunded: {why} -- {carried} bars above {over:.0%} long with "
                    f"positions sized on an earlier bar; re-running every target at "
                    f"{cap:.1%} (the book peaks at {peak:.0%} long)"
                )
                continue
        if steps >= DELEVERAGE_MAX_STEPS:
            print(
                f"Underfunded at {cap:.1%}: {why} -- no exposure makes it "
                f"fundable, returning it as published"
            )
            return finish(as_published, as_published, attempts, 1.0, True)
        step = cap * DELEVERAGE_STEP
        peak = max([0.0] + [long for _, long, _ in strategy._pwb_cap_records])
        if schedule is None and peak > max_leverage and max_leverage / peak < step:
            # Run at one scale, this run measured what the book asks for on
            # the path it takes funded -- more than the refusals as published
            # let through (a third cohort that was always refused).
            cap, steps = max_leverage / peak, steps + 1
            print(
                f"Underfunded: {why} -- stepping every target down to {cap:.1%} "
                f"(the book peaks at {peak:.0%} long once funded)"
            )
            continue
        cap, steps = step, steps + 1
        print(f"Underfunded: {why} -- stepping every target down to {cap:.1%}")


def _perturb_parameter(base_kwargs: dict, param_path: tuple[str, ...], new_value):
    kw = copy.deepcopy(base_kwargs)
    target = kw
    for key in param_path[:-1]:
        target = target[key]
    last_key = param_path[-1]
    target[last_key] = new_value
    return kw


def generate_sensitivity_results(
    base_kwargs: dict,
    run_strategy_once: callable,
    compute_perf_metric: callable,
    scale_factors=None,
):
    if scale_factors is None:
        scale_factors = [0.5, 0.8, 1.0, 1.2, 1.5]

    results = {}
    for key, value in base_kwargs.items():
        if isinstance(value, (int, float)):
            label = key
            base_val = float(value)
            vals, metrics = [], []
            for sf in scale_factors:
                new_val = base_val * sf
                nav = run_strategy_once(
                    _perturb_parameter(base_kwargs, (key,), new_val)
                )
                vals.append(new_val)
                metrics.append(compute_perf_metric(nav))
            results[label] = (vals, metrics)
        elif isinstance(value, list):
            for idx, elem in enumerate(value):
                if not isinstance(elem, (int, float)):
                    continue
                label = f"{key}[{idx}]"
                base_val = float(elem)
                vals, metrics = [], []
                for sf in scale_factors:
                    new_val = base_val * sf
                    nav = run_strategy_once(
                        _perturb_parameter(base_kwargs, (key, idx), new_val)
                    )
                    vals.append(new_val)
                    metrics.append(compute_perf_metric(nav))
                results[label] = (vals, metrics)
    return results
