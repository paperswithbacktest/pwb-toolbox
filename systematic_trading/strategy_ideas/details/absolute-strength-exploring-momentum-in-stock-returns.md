<div align="center">
  <h1>Absolute Strength: Exploring Momentum in Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2638004)

## Trading rules

- Investment universe: NASDAQ, AMEX, NYSE stocks (excluding those priced under $1)
- Monthly stock sorting: value-weighted portfolios based on cumulative returns from t-12 to t-2
- Cumulative return breakpoints: historical distribution of non-overlapping 11-month returns since 1927
- Absolute winners: top 10% of historical distribution
- Absolute losers: bottom 10% of historical distribution
- Strategy: buy absolute winners, sell absolute losers, and rebalance monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2000-2014
- **Annual Return:** 19.7%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.54
- **Annual Standard Deviation:** 29.06%

## Python code

### Backtrader

```python
import backtrader as bt

class AbsoluteMomentum(bt.Strategy):
    params = (
        ('lookback', 12),
        ('top_percentile', 0.1),
        ('bottom_percentile', 0.1),
    )

    def __init__(self):
        self.returns = {}
        for data in self.datas:
            self.returns[data._name] = bt.ind.PctChange(data.close, period=self.p.lookback)

    def next(self):
        winners, losers = [], []
        for data in self.datas:
            if data.close[0] < 1:
                continue
            self.returns[data._name].update()
            ret = self.returns[data._name][0]
            winners.append((ret, data))
            losers.append((ret, data))

        winners.sort(reverse=True)
        losers.sort()
        n_winners = int(len(winners) * self.p.top_percentile)
        n_losers = int(len(losers) * self.p.bottom_percentile)

        self.winners = [data for _, data in winners[:n_winners]]
        self.losers = [data for _, data in losers[:n_losers]]

        for data in self.winners:
            size = self.broker.getcash() / len(self.winners)
            self.order_target_value(data, size)

        for data in self.losers:
            size = self.broker.getcash() / len(self.losers)
            self.order_target_value(data, -size)

        for data in self.datas:
            if data not in self.winners and data not in self.losers:
                self.order_target_value(data, 0)
```

Please note that this code snippet is meant to provide a starting point for the implementation of the Absolute Momentum strategy using Backtrader. You may need to modify the code to fit your specific data input format, and it might be necessary to implement additional data preprocessing and filtering based on the investment universe requirements.