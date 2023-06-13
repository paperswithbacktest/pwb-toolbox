<div align="center">
  <h1>Behavioral Anomalies in Cryptocurrency Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3174421)

## Trading rules

- Investment universe consists of 11 cryptocurrencies
- Momentum factor is prior week’s return for each currency
- Momentum factor is standardized by z-scoring longitudinally
- Portfolio is equally weighted with absolute weight of 10% divided by n
- Weight is positive when the normalized momentum factor is above zero, and negative when below zero
- Portfolio can be net long or short the market, but practical application requires long only strategy
- Portfolio is rebalanced weekly
- Two weighting schemes: equally weighted and risk-based (more information in the paper)

## Statistics

- **Markets Traded:** Cryptocurrencies
- **Period of Rebalancing:** Weekly
- **Backtest period:** 2013-2017
- **Annual Return:** 6.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.78
- **Annual Standard Deviation:** 8.1%

## Python code

### Backtrader

```python
import backtrader as bt
from scipy.stats import zscore

class MyStrategy(bt.Strategy):

    def __init__(self):
        self.inds = {}
        self.universe = ['crypto1', 'crypto2', 'crypto3', 'crypto4', 'crypto5', 'crypto6', 'crypto7', 'crypto8', 'crypto9', 'crypto10', 'crypto11']
        self.portfolio_size = len(self.universe)
        for i, d in enumerate(self.datas):
            self.inds[d] = {}
            self.inds[d]['momentum'] = Momentum(d.close, period=7, plot=False)
            self.inds[d]['momentum_zscore'] = ZScore(self.inds[d]['momentum'], period=200, plot=False)

    def next(self):
        mom_values = [self.inds[d]['momentum_zscore'][0] for d in self.datas]
        mom_values_normalized = zscore(mom_values)

        equal_weights = 0.10 / self.portfolio_size

        weights = [equal_weights if mom > 0 else - equal_weights for mom in mom_values_normalized]

        for i, d in enumerate(self.datas):
            self.order_target_percent(d, target=weights[i])

class Momentum(bt.Indicator):

    lines = ('momentum',)

    def __init__(self, close, period):
        self.lines.momentum = close - close(-period)

class ZScore(bt.Indicator):

    lines = ('zscore',)
    params = dict(period=200)

    def __init__(self, momentum, period):
        self.lines.zscore = zscore(momentum.get(size=period))

    def next(self):
        self.lines.zscore = zscore(self.l.momentum.get(size=self.p.period))
```