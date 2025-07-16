import backtrader as bt
import pandas as pd
import pwb_toolbox.datasets as pwb_ds


def run_strategy(signal, signal_kwargs, portfolio, symbols, start_date, leverage, cash):
    """Run a tactical asset allocation strategy with Backtrader."""
    # Load the data from https://paperswithbacktest.com/datasets
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
    for symbol in symbols:
        data = bt.feeds.PandasData(dataname=pivot_df[symbol].copy())
        cerebro.adddata(data, name=symbol)
    cerebro.addstrategy(
        portfolio,
        total_days=len(trading_days),
        leverage=0.9,
        signal_cls=signal,
        signal_kwargs=signal_kwargs,
    )
    cerebro.broker.set_cash(cash)
    strategy = cerebro.run()[0]
    return strategy
