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
    for symbol in pivot_df.columns.levels[0]:
        data = bt.feeds.PandasData(dataname=pivot_df[symbol].copy())
        cerebro.adddata(data, name=symbol)
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
        commission = np.mean(list(pwb_bt.get_commissions(symbols).values()))
        print(f"Estimated commission: {commission:.6f}")
        broker_kwargs["commission"] = commission
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
