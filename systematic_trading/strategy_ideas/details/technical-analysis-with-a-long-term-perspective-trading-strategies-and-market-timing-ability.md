<div align="center">
  <h1>Technical Analysis with a Long Term Perspective: Trading Strategies and Market Timing Ability</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1833613)

## Trading rules

- Trade S&P 500 index via futures or ETFs
- Utilize two Simple Moving Averages (SMAs) based on short and long intervals
- Identify upward trend when short SMA is above long SMA, and downward trend when short SMA is below long SMA
- Test 23 different lengths for short SMA (1-100 days) and 48 different lengths for long SMA (5-990 days)
- Optimize SMA rule selection based on 4-year performance
- Apply optimal strategy during trading period (assumed 1-day)
- Update selection period daily, using results for the trading session

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1994-2008
- **Annual Return:** 14.6%
- **Maximum Drawdown:** None
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 17.41%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import datetime

class SMACrossOptimized(bt.Strategy):
    params = (
        ('short_sma_range', range(1, 101, 23)),
        ('long_sma_range', range(5, 991, 48)),
        ('optimization_period', 4 * 365),  # 4 years in days
    )

    def __init__(self):
        self.sma_short = {}
        self.sma_long = {}
        for short_period in self.params.short_sma_range:
            for long_period in self.params.long_sma_range:
                if short_period >= long_period:
                    continue
                self.sma_short[(short_period, long_period)] = bt.indicators.SimpleMovingAverage(
                    self.data.close, period=short_period
                )
                self.sma_long[(short_period, long_period)] = bt.indicators.SimpleMovingAverage(
                    self.data.close, period=long_period
                )

    def next(self):
        if len(self) < self.params.optimization_period:
            return
        best_pnl = -np.inf
        best_params = None
        for short_period, long_period in self.sma_short.keys():
            pnl = self.data.close[0] - self.data.close[-self.params.optimization_period]
            if self.sma_short[(short_period, long_period)][0] > self.sma_long[(short_period, long_period)][0]:
                pnl *= -1
            if pnl > best_pnl:
                best_pnl = pnl
                best_params = (short_period, long_period)
        short_sma = self.sma_short[best_params]
        long_sma = self.sma_long[best_params]
        if short_sma[0] > long_sma[0] and not self.position:
            self.buy()
        elif short_sma[0] < long_sma[0] and self.position:
            self.sell()

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SMACrossOptimized)
    data = bt.feeds.YahooFinanceData(
        dataname='^GSPC',  # S&P 500
        fromdate=datetime.datetime(1990, 1, 1),
        todate=datetime.datetime(2021, 12, 31),
        buffered=True
    )
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.FixedSize, stake=10)
    cerebro.run()
    cerebro.plot()
```

Please note that you’ll need to adjust the data source and date range as necessary for your specific use case. This code assumes the use of Backtrader library for Python, and it is not tested in a live environment.