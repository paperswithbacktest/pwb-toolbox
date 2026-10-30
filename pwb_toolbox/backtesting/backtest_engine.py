import copy
import os
import backtrader as bt
import itertools
import pandas as pd
import numpy as np
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds

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


# What a fundable book is allowed to ask for. The missing 1 % is the commission:
# a book at exactly 100 % has no cash left to pay for the trade that got it
# there, so backtrader refuses the order and the NAV stops moving.
TARGET_GROSS = 0.99

# Fallback step, applied when scaling to TARGET_GROSS was not enough, and the
# number of times it may be applied before the run is given up on.
DELEVERAGE_STEP = 0.90
DELEVERAGE_MAX_STEPS = 5

# Share of orders a run may fail to fund before it counts as underfunded. An
# isolated rejection on a gap day is noise; a systematic one freezes the NAV.
MARGIN_TOLERANCE = 0.02
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
    * ``min_value`` -- the low-water mark of the NAV itself. A geared book that
      loses enough does not merely draw down, it goes through zero.
    """

    def start(self):
        self.margin = 0
        self.submitted = 0
        self.min_cash = None
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

    def get_analysis(self):
        submitted = max(self.submitted, 1)
        return {
            "margin": self.margin,
            "submitted": self.submitted,
            "reject_rate": self.margin / submitted,
            "min_cash": self.min_cash,
            "min_value": self.min_value,
        }


def _underfunded(audit: dict, tolerance: float) -> bool:
    """True when the run outgrew the account: refused, in debit, or wiped out.

    The margin check itself stays in force -- this only decides whether the
    same strategy is worth re-running smaller.
    """
    if audit["reject_rate"] > tolerance:
        return True
    if audit["min_cash"] is not None and audit["min_cash"] < 0:
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
    that stopped printing may still be held or sold.

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


def _with_exposure_cap(strategy_cls, cap: float):
    """Subclass ``strategy_cls`` to scale, and record, every target it asks for.

    Acts on the order, not on a ``leverage`` parameter, because declaring one
    does not mean honouring it: both strategies that went flat on the margin
    cliff declare ``leverage`` and then call ``order_target_percent`` with a
    literal 1.0, and 1 803 of the 5 831 published strategies declare no such
    parameter at all. Scaling the request is the only lever that always exists.

    ``requested_gross`` is the high-water mark of what the strategy asked for
    before scaling, which is what sizes the next attempt: a book asking for
    200 % needs halving, and guessing that by steps would cost five backtests.

    The wrapper's own state lives under ``_pwb_cap_*`` names. It used to be
    ``self._targets``, ``self._record`` and ``self._scaling``, set *after* the
    strategy's ``__init__`` had run: a strategy keeping its target book in
    ``self._targets`` found it replaced by an empty dict, one defining its own
    ``_record(...)`` had it called with the wrapper's two arguments, and 21 of
    the published strategies use one of those names. A subclass that is not
    the strategy's author must not pick the names its author would.
    """

    class _Capped(strategy_cls):
        exposure_cap = cap

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pwb_cap_targets: dict = {}
            self._pwb_cap_scaling = False
            self.requested_gross = 0.0

        def _pwb_cap_record(self, data, share):
            self._pwb_cap_targets[getattr(data, "_name", id(data))] = abs(share)
            gross = sum(self._pwb_cap_targets.values())
            if gross > self.requested_gross:
                self.requested_gross = gross

        def order_target_percent(self, data=None, target=0.0, **kwargs):
            # backtrader's own order_target_percent multiplies by the NAV and
            # calls order_target_value, which lands back here. Without the
            # guard the cap is applied twice -- 0.495 became 0.245 -- and the
            # recorded gross is overwritten by the already-scaled figure.
            if self._pwb_cap_scaling:
                return super().order_target_percent(
                    data=data, target=target, **kwargs
                )
            self._pwb_cap_record(data, target)
            self._pwb_cap_scaling = True
            try:
                return super().order_target_percent(
                    data=data, target=target * cap, **kwargs
                )
            finally:
                self._pwb_cap_scaling = False

        def order_target_value(self, data=None, target=0.0, **kwargs):
            if self._pwb_cap_scaling:
                return super().order_target_value(
                    data=data, target=target, **kwargs
                )
            value = self.broker.getvalue()
            self._pwb_cap_record(data, target / value if value else 0.0)
            self._pwb_cap_scaling = True
            try:
                return super().order_target_value(
                    data=data, target=target * cap, **kwargs
                )
            finally:
                self._pwb_cap_scaling = False

    _Capped.__name__ = f"{strategy_cls.__name__}Capped{round(cap * 100)}"
    _Capped.__qualname__ = _Capped.__name__
    return _Capped


def _next_cap(cap: float, requested_gross: float, steps: int):
    """The exposure to try next, or None once the attempts are spent.

    The first retry is computed, not guessed: a strategy that asked for 200 %
    gross is scaled to fit TARGET_GROSS in one go. Only if that still cannot be
    funded does it fall back to stepping down, which is for the cases where the
    shortfall is not gross exposure -- a short leg posting margin, say.
    """
    if steps == 0 and requested_gross > TARGET_GROSS:
        return TARGET_GROSS / requested_gross
    if steps >= DELEVERAGE_MAX_STEPS:
        return None
    return cap * DELEVERAGE_STEP


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

    With ``deleverage`` on, a run that cannot fund what the strategy asks for is
    repeated with its gross exposure stepped down the ``EXPOSURE_LADDER`` until
    it can. The margin check stays in force: a fully invested book plus a
    commission costs more than the account holds, so backtrader refuses every
    rebalance and the NAV goes flat -- which then publishes as a Sharpe of zero,
    or of NaN, rather than as the error it is.

    The applied exposure is on the returned strategy as ``exposure_cap``, and
    the funding audit as ``funding_audit``. A run that stays underfunded at the
    bottom of the ladder is returned with both set, so the caller can refuse it
    rather than record a number.
    """
    # The default observers (Broker, BuySell, Trades) exist for plotting and
    # cost about a tenth of the engine loop; nothing in the harness or in the
    # published strategies reads them, and the dozen strategies that build
    # their own Cerebro already pass ``stdstats=False``. A caller who plots
    # passes ``cerebro_kwargs={"stdstats": True}``.
    cerebro_kwargs = {"stdstats": False, **(cerebro_kwargs or {})}
    broker_kwargs = broker_kwargs or {}
    # Load the data from https://paperswithbacktest.com/datasets -- once, and
    # reused across attempts, because the ladder must not re-download anything.
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

    cap, steps, strategy, as_published = 1.0, 0, None, None
    while True:
        # Engine configuration
        cerebro = bt.Cerebro(**cerebro_kwargs)
        # Keyed by feed name, because that is what ``addcommissioninfo(name=...)``
        # matches on, and what the scheme reads the bar date from.
        feeds = {}
        for symbol in pivot_df.columns.levels[0]:
            data = ArrayPandasData(dataname=pivot_df[symbol].copy())
            cerebro.adddata(data, name=symbol)
            feeds[symbol] = data
        # Strategy
        cerebro.addstrategy(
            _with_exposure_cap(strategy_cls, cap),
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
        audit = strategy.analyzers.funding.get_analysis()
        audit["requested_gross"] = strategy.requested_gross
        strategy.exposure_cap = cap
        strategy.funding_audit = audit
        strategy.fill_audit = strategy.analyzers.fill.get_analysis()
        if strategy.fill_audit:
            worst = max(strategy.fill_audit.items(), key=lambda kv: kv[1]["bars"])
            print(
                f"Held while absent: {len(strategy.fill_audit)} symbols with a position "
                f"in a year without a bar, e.g. {worst[0]} {worst[1]['years'][0]}-"
                f"{worst[1]['years'][-1]} ({worst[1]['bars']} bars)"
            )
        if as_published is None:
            as_published = strategy

        if not _underfunded(audit, margin_tolerance):
            if steps:
                print(
                    f"Funded at {cap:.1%} of the requested exposure "
                    f"(the book asked for {strategy.requested_gross:.0%} gross)"
                )
            return strategy
        if not deleverage:
            return strategy

        nxt = _next_cap(cap, strategy.requested_gross, steps)
        print(
            f"Underfunded at {cap:.1%} of a {strategy.requested_gross:.0%} gross "
            f"book: {audit['margin']}/{audit['submitted']} orders refused for "
            f"margin"
            + (
                f", min cash {audit['min_cash']:,.0f}"
                if audit["min_cash"] is not None and audit["min_cash"] < 0
                else ""
            )
            + (
                f", NAV through zero ({audit['min_value']:,.0f})"
                if audit["min_value"] is not None and audit["min_value"] <= 0
                else ""
            )
            + (
                f" -- retrying at {nxt:.1%}"
                if nxt
                else " -- no exposure makes it fundable, returning it as published"
            )
        )
        if nxt is None:
            # Nothing was found that works, so the honest record is the
            # strategy as published, not an arbitrarily shrunk version of it
            # that is neither what was published nor fundable either.
            return as_published
        cap, steps = nxt, steps + 1


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
