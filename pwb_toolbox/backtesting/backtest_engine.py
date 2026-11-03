import bisect
import copy
import json
import os
import itertools
import pandas as pd
import numpy as np
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds

from ..engine import load as _load_engine

bt = _load_engine()  # backtrader by default, Tradewind on request; see pwb_toolbox.engine
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
    # ticker that sits in the cost table at 119.6 bp.
    schedules, summary = pwb_bt.get_cost_schedules(
        priced,
        start_date=start_date,
        end_date=end_date,
        measurable=pwb_bt.equity_symbols(symbols),
        active_years=active_years,
        currencies=pwb_bt.currency_symbols(symbols),
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
        broker.addcommissioninfo(scheme, name=symbol)

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
        cash = self.strategy.broker.get_cash()
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


def _pit_membership(symbols, present: pd.DataFrame, trading_days) -> "_Membership | None":
    """Where each name a point-in-time universe brought in sits outside it.

    ``present`` is the panel's row mask before any fill. A bar is outside when
    the name was not a member on that session *and* has no price row: the rows
    ``apply_pit_membership`` keeps (its as-of tolerance, a member's real bar)
    stay tradable, and so does a hole in a member's prices -- that one is a
    data gap, not an exit. Names the caller listed itself (``["sp500", "SPY"]``)
    are never cut, as in ``get_pricing``.
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    _, spec, added, explicit = pwb_ds._resolve_universe(list(symbols))
    if spec is None:
        return None
    names = [s for s in present.columns if s in added and s not in explicit]
    if not names:
        return None
    from pwb_toolbox.datasets.pit_universe import membership_mask

    member = membership_mask(trading_days, names, *spec).to_numpy()
    rows = present[names].reindex(trading_days, fill_value=False).to_numpy(dtype=bool)
    listed = np.maximum.accumulate(rows, axis=0)  # from the first real bar on
    out = ~member & ~rows & listed
    return _Membership(trading_days, pd.DataFrame(out, index=trading_days, columns=names))


def _flatten_out_bars(pivot_df: pd.DataFrame, membership: "_Membership") -> None:
    """Make every bar outside the universe a flat bar at the last member close.

    The forward fill copies the whole last bar, its open included, so an order
    filled on the first bar outside would trade at a price already a day old.
    A flat bar at the last close is the price the liquidation gets, and it
    earns nothing while the name is away.
    """
    names = list(membership.out)
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


def _refuse_outside_universe(broker, membership: "_Membership", state: dict) -> dict:
    """Make ``broker`` reject any order on a name outside its point-in-time universe.

    The bars outside are a flat line (``_flatten_out_bars``), with a volatility,
    a beta and a correlation of zero: a low-volatility or a minimum-variance
    sort picks them first. Accepting the order would hold a position that
    earns nothing while the name is away and then takes, in one bar, the whole
    move it made in the meantime (CIT on 2009-12-10, 0.7 to 29 dollars). A
    real broker answers ``Rejected`` for an instrument the account may not
    trade, and the strategy is notified the same way. The liquidation the
    harness itself places at the exit passes (``state["liquidating"]``).

    Returns the audit, filled as the run goes: ``{symbol: {"orders": n,
    "first": date, "last": date}}``.
    """
    audit = {}
    original = broker.submit

    def submit(order, check=True):
        if not state.get("liquidating"):
            data = order.data
            symbol = getattr(data, "_name", None)
            today = data.datetime.date(0)
            if membership.is_out(symbol, today):
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


def _with_exposure_cap(strategy_cls, cap: float = 1.0, schedule=None, membership=None, guard=None):
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
    open orders are filled. ``requested_long`` and ``requested_gross`` are the
    peaks of that record. 0.1.31-0.1.42 kept a target per name that only
    another target could reset, so a name exited by ``close()``, by size or
    through a refused order stayed in the sum for good: 4.9 for a book that
    never held more than 0.98 (``tests/test_exposure_cap.py``).

    With ``membership``, a position in a name that leaves its point-in-time
    universe is closed on the first bar outside (filled at the last member
    close, see ``_flatten_out_bars``); ``guard`` is the flag that lets that one
    order past ``_refuse_outside_universe``.

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
            self._pwb_ms_next = 0
            self._pwb_ms_watch = set()
            self._pwb_ms_filled = set()
            self._pwb_ms_orders = {}
            self._pwb_ms_feeds = None
            self.requested_gross = 0.0
            self.requested_long = 0.0
            self.membership_liquidations = {}
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
            self._pwb_cap_req[getattr(data, "_name", None) or id(data)] = (data, float(weight))
            scale = cap
            if days and day is not None:
                i = bisect.bisect_right(days, day) - 1
                if i >= 0:
                    scale *= scales[i]
            if scale < 1.0 and weight and day is not None:
                self._pwb_cap_applied[day] = min(scale, self._pwb_cap_applied.get(day, 1.0))
            return scale

        def order_target_percent(self, data=None, target=0.0, **kwargs):
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
            return self._pwb_track(super().buy(*args, **kwargs))

        def sell(self, *args, **kwargs):
            return self._pwb_track(super().sell(*args, **kwargs))

        def _pwb_track(self, order):
            if order is not None:
                name = getattr(order.data, "_name", None) or id(order.data)
                self._pwb_cap_live[name] = order.data
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
            value = self.broker.getvalue()
            for name, data in list(self._pwb_cap_live.items()):
                held = self._pwb_cap_held(name, data)
                if held is None:
                    del self._pwb_cap_live[name]
                    self._pwb_cap_orders.pop(name, None)
                    continue
                if name in req or value <= 0:
                    continue
                weight = held * float(data.close[0]) / value
                if weight > 0:
                    long += weight
                else:
                    short -= weight
            self._pwb_cap_records.append((self._pwb_cap_day, long, short))
            self.requested_long = max(self.requested_long, long)
            self.requested_gross = max(self.requested_gross, long + short)

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
                guard["liquidating"] = True
                try:
                    order = self.close(data)
                finally:
                    guard["liquidating"] = False
                self._pwb_ms_orders[name] = order
                entry = self.membership_liquidations.setdefault(
                    name, {"orders": 0, "first": day, "prices": []}
                )
                entry["orders"] += 1

        def notify_order(self, order):
            if membership is not None and order.status == order.Completed:
                name = getattr(order.data, "_name", None)
                if name in membership.out:
                    self._pwb_ms_filled.add(name)
                    mine = self._pwb_ms_orders.get(name)
                    if mine is not None and mine.ref == order.ref:
                        self.membership_liquidations[name]["prices"].append(
                            order.executed.price
                        )
            return super().notify_order(order)

        # -- end of each bar --------------------------------------------------------
        def _pwb_after_bar(self):
            self._pwb_cap_close_bar()
            if membership is not None and self.datas:
                self._pwb_ms_step()

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

    **Point-in-time universes** (``"sp500"``, ``"liquid1000"``). A name that
    leaves the universe has no row until it comes back; the forward fill used
    to make that a flat line the strategy could buy and hold, and the move the
    name made while away then landed in one bar at its return. Now a position
    is closed on the first bar outside, at the last member close; any other
    order on the name is refused (``Rejected``) until it is a member again. A
    hole in the prices of a *member* is still forward-filled. The refusals and
    liquidations are on the returned strategy as ``membership_audit``. The
    flat bars are still in the feed -- a strategy can skip them with
    ``BaseStrategy.is_tradable`` -- so a screen that keeps choosing them ends
    up partly in cash rather than in a phantom.

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
    returned. ``max_leverage`` cannot exceed 1: backtrader refuses at execution
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
    )
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
    pivot_df = pivot_df.reindex(trading_days)
    pivot_df.ffill(inplace=True)  # forward-fill holidays
    pivot_df.bfill(inplace=True)  # back-fill leading IPO gaps
    all_years = set(trading_days.year)
    inactive = {
        symbol: all_years - years for symbol, years in active_years.items()
        if all_years - years
    }
    membership = _pit_membership(symbols, present, trading_days)
    if membership is not None:
        _flatten_out_bars(pivot_df, membership)

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
                strategy_cls, cap, schedule=schedule, membership=membership, guard=guard
            ),
            total_days=len(trading_days),
            indicator_cls=indicator_cls,
            indicator_kwargs=indicator_kwargs,
            **strategy_kwargs,
        )
        cerebro.addanalyzer(FundingAudit, _name="funding")
        cerebro.addanalyzer(FillAudit, _name="fill", inactive=inactive)
        # Broker. ``_apply_broker_kwargs`` pops what it consumes, so each
        # attempt gets its own copy -- otherwise the second run of a
        # de-leveraging sequence would silently lose the caller's commission
        # and fall back to the measured per-symbol scheme.
        run_broker_kwargs = copy.deepcopy(broker_kwargs)
        cerebro.broker.set_cash(cash)
        if "commission" not in run_broker_kwargs:
            _apply_per_symbol_commissions(
                cerebro.broker,
                symbols,
                start_date,
                enable_impact=enable_impact,
                feeds=feeds,
                end_date=pivot_df.index.max(),
                active_years=active_years,
            )
        _apply_broker_kwargs(cerebro.broker, run_broker_kwargs)
        # Inner guard first: an order dated before the listing is refused by
        # the listing guard and counted there, as before the membership one.
        refused_outside = (
            _refuse_outside_universe(cerebro.broker, membership, guard)
            if membership is not None
            else {}
        )
        listing_audit = (
            _refuse_before_listing(cerebro.broker, first_bar)
            if refuse_before_listing
            else {}
        )
        # Run the strategy
        strategy = cerebro.run()[0]
        strategy.listing_audit = listing_audit
        if listing_audit:
            worst = max(listing_audit.items(), key=lambda kv: kv[1]["orders"])
            refused = sum(entry["orders"] for entry in listing_audit.values())
            print(
                f"Refused before listing: {refused} orders on {len(listing_audit)} "
                f"symbols, e.g. {worst[0]} {worst[1]['first']} to {worst[1]['last']} "
                f"(first bar {first_bar[worst[0]].date()})"
            )
        strategy.membership_audit = {
            "refused": refused_outside,
            "liquidated": strategy.membership_liquidations,
        }
        if refused_outside or strategy.membership_liquidations:
            refused = sum(entry["orders"] for entry in refused_outside.values())
            print(
                f"Out of universe: {refused} orders refused on {len(refused_outside)} "
                f"symbols, {len(strategy.membership_liquidations)} positions closed "
                f"at their last member price"
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
            "membership": {
                "refused_orders": sum(
                    e["orders"] for e in strategy.membership_audit["refused"].values()
                ),
                "refused_symbols": len(strategy.membership_audit["refused"]),
                "liquidated_symbols": len(strategy.membership_audit["liquidated"]),
            },
        }
        strategy.exposure_cap = report["exposure_cap"]
        strategy.requested_long = as_published.requested_long
        strategy.requested_gross = as_published.requested_gross
        strategy.run_report = report
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
            "reject_rate": round(funding["reject_rate"], 6),
            "min_cash_ratio": (
                None if funding["min_cash_ratio"] is None
                else round(funding["min_cash_ratio"], 6)
            ),
            "underfunded": bool(underfunded),
        }))
        return strategy

    cap, schedule, steps, attempts, as_published = 1.0, None, 0, 0, None
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
        if steps >= DELEVERAGE_MAX_STEPS:
            print(
                f"Underfunded at {cap:.1%}: {why} -- no exposure makes it "
                f"fundable, returning it as published"
            )
            return finish(as_published, as_published, attempts, 1.0, True)
        cap, steps = cap * DELEVERAGE_STEP, steps + 1
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
