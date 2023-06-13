<div align="center">
  <h1>Cross-Asset Signals and Time Series Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2891434)

## Trading rules

- Investment universe: 20 leading industrial countries’ bond and equity indexes
- Condition 1: Long position in bonds when last 12-month equity returns are negative and bond returns are positive
- Condition 2: Long position in equities when both last 12-month equity and bond returns are positive
- Condition 3: No position taken, capital held in dollar-denominated margin account earning US risk-free rate
- Holding period: One month for both equities and bonds
- Portfolios: Targeted for 10% volatility, consisting of bond and equity indexes for each country
- Country shares: Equally-weighted within the final portfolio

## Statistics

- **Markets Traded:** Bonds, equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1980-2015
- **Annual Return:** 6.5%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.65
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt

class CrossAssetMomentum(bt.Strategy):
    params = (
        ('lookback_period', 12),
        ('target_volatility', 0.1),
    )

    def __init__(self):
        self.equity_returns = {}
        self.bond_returns = {}

        for d in self.getdatanames():
            if 'equity' in d:
                self.equity_returns[d] = bt.ind.PctChange(self.getdatabyname(d), period=self.params.lookback_period)
            if 'bond' in d:
                self.bond_returns[d] = bt.ind.PctChange(self.getdatabyname(d), period=self.params.lookback_period)

    def next(self):
        for country in range(20):
            equity_data = self.equity_returns[f'country{country}_equity']
            bond_data = self.bond_returns[f'country{country}_bond']

            if equity_data[-1] < 0 and bond_data[-1] > 0:
                target_size = self.broker.getvalue() * self.params.target_volatility / len(self.equity_returns) / bond_data.std()
                self.order_target_size(f'country{country}_bond', target_size)
                self.order_target_size(f'country{country}_equity', 0)
            elif equity_data[-1] > 0 and bond_data[-1] > 0:
                target_size = self.broker.getvalue() * self.params.target_volatility / len(self.equity_returns) / equity_data.std()
                self.order_target_size(f'country{country}_equity', target_size)
                self.order_target_size(f'country{country}_bond', 0)
            else:
                self.order_target_size(f'country{country}_bond', 0)
                self.order_target_size(f'country{country}_equity', 0)
```

To use this code, you would need to create a Backtrader `Cerebro` instance, add your data feeds (20 bond and 20 equity indexes) with their respective names, and then add this strategy to the Cerebro instance. Note that this code assumes that the data feeds are named according to the format: `country{country_number}_equity` and `country{country_number}_bond`.