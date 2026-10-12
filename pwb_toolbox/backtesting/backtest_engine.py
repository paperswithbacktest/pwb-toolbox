import copy
import backtrader as bt
import itertools
import pandas as pd
import numpy as np
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds


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
    broker, symbols, start_date, enable_impact=False, feeds=None, end_date=None
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
    """
    priced = list(feeds) if feeds else list(symbols)
    schedules, summary = pwb_bt.get_cost_schedules(
        priced, start_date=start_date, end_date=end_date
    )
    lambdas = pwb_bt.load_lambda_params() if enable_impact else {}
    year = int(str(start_date)[:4])

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
    span = f"{year}" if end_date is None else f"{year}-{str(end_date)[:4]}"
    print(
        f"Commissions: {len(rates)} symbols, {span}, "
        f"{np.median(rates) * 1e4:.1f} bp median at {year}, "
        f"{min(rates) * 1e4:.1f}-{max(rates) * 1e4:.1f} bp range ({detail})"
    )


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
):
    """Run a tactical asset allocation strategy with Backtrader."""
    # Load the data from https://paperswithbacktest.com/datasets
    cerebro_kwargs = cerebro_kwargs or {}
    broker_kwargs = broker_kwargs or {}
    # Engine configuration
    cerebro = bt.Cerebro(**cerebro_kwargs)
    # Universe
    pivot_df = pwb_ds.get_pricing(
        symbol_list=symbols,
        fields=["open", "high", "low", "close"],
        start_date=start_date,
        extend=True,  # Extend the dataset with proxy data
    )
    # Create trading-day index (optional but keeps Cerebro happy)
    trading_days = pd.bdate_range(pivot_df.index.min(), pivot_df.index.max())
    pivot_df = pivot_df.reindex(trading_days)
    pivot_df.ffill(inplace=True)  # forward-fill holidays
    pivot_df.bfill(inplace=True)  # back-fill leading IPO gaps
    cerebro = bt.Cerebro()
    # Keyed by feed name, because that is what ``addcommissioninfo(name=...)``
    # matches on, and what the scheme reads the bar date from.
    feeds = {}
    for symbol in pivot_df.columns.levels[0]:
        data = bt.feeds.PandasData(dataname=pivot_df[symbol].copy())
        cerebro.adddata(data, name=symbol)
        feeds[symbol] = data
    # Strategy
    cerebro.addstrategy(
        strategy_cls,
        total_days=len(trading_days),
        indicator_cls=indicator_cls,
        indicator_kwargs=indicator_kwargs,
        **strategy_kwargs,
    )
    # Broker
    cerebro.broker.set_cash(cash)
    if "commission" not in broker_kwargs:
        _apply_per_symbol_commissions(
            cerebro.broker,
            symbols,
            start_date,
            enable_impact=enable_impact,
            feeds=feeds,
            end_date=pivot_df.index.max(),
        )
    _apply_broker_kwargs(cerebro.broker, broker_kwargs)
    # Run the strategy
    strategy = cerebro.run()[0]
    return strategy


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
