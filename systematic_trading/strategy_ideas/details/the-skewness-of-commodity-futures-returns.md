<div align="center">
  <h1>The Skewness of Commodity Futures Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2671165)

## Trading rules

- 27 futures contracts on commodities as investment universe
- Calculate skewness from daily returns (12-month lookback)
- Sort commodities into quintiles based on skewness
- Long bottom 20% (lowest skewness) and short top 20% (highest skewness)
- Equally weighted portfolio
- Rebalance monthly

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1987-2014
- **Annual Return:** 8.01%
- **Maximum Drawdown:** -29.73%
- **Sharpe Ratio:** 0.79
- **Annual Standard Deviation:** 10.2%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import scipy.stats as stats

class SkewnessStrategy(bt.Strategy):
    params = (
        ('lookback', 252),
        ('rebalance_days', 30),
    )

    def __init__(self):
        self.counter = 0
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['daily_returns'] = bt.indicators.Returns(d.close, name='daily_returns')
            self.inds[d]['skewness'] = bt.indicators.Skewness(self.inds[d]['daily_returns'], period=self.params.lookback)

    def next(self):
        self.counter += 1
        if self.counter % self.params.rebalance_days != 0:
            return
        skews = [(d, self.inds[d]['skewness'][0]) for d in self.datas]
        skews.sort(key=lambda x: x[1])
        num_assets = len(skews)
        quintile_size = num_assets // 5
        long_skews = skews[:quintile_size]
        short_skews = skews[-quintile_size:]
        long_weight = 1.0 / len(long_skews)
        short_weight = -1.0 / len(short_skews)
        for d in self.datas:
            if d in [x[0] for x in long_skews]:
                self.order_target_percent(d, target=long_weight)
            elif d in [x[0] for x in short_skews]:
                self.order_target_percent(d, target=short_weight)
            else:
                self.order_target_percent(d, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add data feeds for the 27 commodity futures contracts here
    # Example:
    # data_feed = bt.feeds.GenericCSVData(
    #     dataname="path/to/data.csv",
    #     dtformat="%Y-%m-%d",
    #     openinterest=-1,
    #     timeframe=bt.TimeFrame.Days,
    #     compression=1
    # )
    # cerebro.adddata(data_feed)
    cerebro.addstrategy(SkewnessStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())
```