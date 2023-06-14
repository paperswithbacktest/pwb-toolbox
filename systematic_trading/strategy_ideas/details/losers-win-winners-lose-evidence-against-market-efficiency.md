<div align="center">
  <h1>Losers Win, Winners Lose: Evidence Against Market Efficiency</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2508088)

## Trading rules

- Investment universe: All available ETFs
- Sort ETFs into deciles by historical performance
- Weekly formation period used for decile sorting
- Winner ETFs: Top-performing decile
- Loser ETFs: Poorest-performing decile
- Equal weighting for ETFs in each decile
- Form weekly loser minus winner portfolio

## Statistics

- **Markets Traded:** ETFs
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1996-2005
- **Annual Return:** 19.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 26%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime
import pandas as pd

class ETFReversal(bt.Strategy):
    params = dict(
        formation_period=5,  # weekly formation period
    )

    def __init__(self):
        self.inds = dict()
        for d in self.datas:
            self.inds[d] = dict()
            self.inds[d]['roc'] = bt.indicators.ROC(d.close, period=self.params.formation_period)

    def next(self):
        # Get the date for the current week
        current_date = self.datetime.date(0)

        # Sort ETFs into deciles by historical performance
        etfs_performance = {data: self.inds[data]['roc'][0] for data in self.datas}
        sorted_etfs = sorted(etfs_performance, key=etfs_performance.get, reverse=True)
        decile_size = len(sorted_etfs) // 10

        # Select top and bottom decile ETFs
        winner_etfs = sorted_etfs[:decile_size]
        loser_etfs = sorted_etfs[-decile_size:]

        # Determine equal weight for ETFs in each decile
        winner_weight = 1 / len(winner_etfs)
        loser_weight = 1 / len(loser_etfs)

        # Adjust positions
        for data in self.datas:
            if data in winner_etfs:
                self.order_target_percent(data, -winner_weight)
            elif data in loser_etfs:
                self.order_target_percent(data, loser_weight)
            else:
                self.order_target_percent(data, 0)

# Backtrader Cerebro instance
cerebro = bt.Cerebro()

# Add data feeds
# Assumes 'all_etfs_data' is a dictionary with key-value pairs: {'ETF_symbol': pandas_dataframe}
for symbol, data in all_etfs_data.items():
    data_feed = bt.feeds.PandasData(dataname=data, name=symbol)
    cerebro.adddata(data_feed)

# Add the strategy
cerebro.addstrategy(ETFReversal)

# Set initial cash, broker, and run
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)
results = cerebro.run()
```

Please note that you will need to provide your own data for ‘all_etfs_data’ in the form of a dictionary with key-value pairs: {‘ETF_symbol’: pandas_dataframe}. The provided code assumes that you have data feeds prepared in the pandas DataFrame format.