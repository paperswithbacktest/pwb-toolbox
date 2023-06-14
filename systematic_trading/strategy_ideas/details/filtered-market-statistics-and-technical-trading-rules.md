<div align="center">
  <h1>Filtered Market Statistics and Technical Trading Rules</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2260609)

## Trading rules

- Investment universe: S&P 500 Index tracking instrument (ETF, CFD, or future)
- Define “Runs”: Consecutive gaining or losing trading days
- Long position: Go 100% long in SPX at market close when the index has been down for n days (n = 2)
- Short position: Switch to 100% short in SPX at market close when the index has been up for n days (n = 2)
- Dynamic filter: Remove noisy days with Filter Threshold
- Filter Threshold: d = 20% of SPX daily return standard deviation over last 60-day rolling window
- Threshold updates: Calculate threshold daily, excluding trading days with absolute daily movement lower than Filter Threshold

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1990-2012
- **Annual Return:** 9.77%
- **Maximum Drawdown:** -26.7%
- **Sharpe Ratio:** 0.31
- **Annual Standard Deviation:** 18.6%

## Python code

### Backtrader

```python
import backtrader as bt

class FilteredReversalStrategy(bt.Strategy):
    params = (
        ('n', 2),
        ('filter_percent', 0.2),
        ('lookback_period', 60),
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.daily_returns = self.dataclose / self.dataclose(-1) - 1
        self.runs = 0

    def next(self):
        std_dev = bt.indicators.StdDev(self.daily_returns, period=self.params.lookback_period)
        filter_threshold = self.params.filter_percent * std_dev[0]

        if abs(self.daily_returns[0]) < filter_threshold:
            return

        if self.daily_returns[0] > 0:
            self.runs = self.runs + 1 if self.runs > 0 else 1
        else:
            self.runs = self.runs - 1 if self.runs < 0 else -1

        current_position = self.getposition().size

        if self.runs <= -self.params.n and current_position <= 0:
            self.order_target_percent(target=1)
        elif self.runs >= self.params.n and current_position >= 0:
            self.order_target_percent(target=-1)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    data = bt.feeds.YourSPXDataFeed(dataname='SPX')
    cerebro.adddata(data)
    cerebro.addstrategy(FilteredReversalStrategy)
    cerebro.run()
```

Replace `YourSPXDataFeed` with the appropriate data feed class for the S&P 500 index tracking instrument (ETF, CFD, or future) you are using.