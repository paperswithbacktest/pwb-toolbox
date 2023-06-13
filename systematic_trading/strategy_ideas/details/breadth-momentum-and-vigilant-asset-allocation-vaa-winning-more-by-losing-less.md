<div align="center">
  <h1>Breadth Momentum and Vigilant Asset Allocation (VAA): Winning More by Losing Less</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624)

## Trading rules

- Investment universe: 10 ETFs representing key asset classes
    - US Stocks
    - European Stocks
    - Japanese Stocks
    - Emerging Market Stocks
    - US REITs
    - International REITs
    - US Intermediate Treasuries
    - US Long-term Treasuries
    - Commodities
    - Gold
- Weekly asset class sorting:
    - Based on 6-month momentum
    - Select top 5 assets
- Minimum variance calculation:
    - Compute asset class weights for the next week
    - Utilize 60-day historical volatilities and correlations
- Portfolio volatility prediction:
    - Estimate overall portfolio volatility
    - Based on min. variance algorithm-derived weights and historical data
    - Rescale portfolio to target 8% volatility
- Weekly execution:
    - Perform steps and rebalance portfolio every week

## Statistics

- **Markets Traded:** Bonds, commodities, equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1995-2012
- **Annual Return:** 16.91%
- **Maximum Drawdown:** -9.56%
- **Sharpe Ratio:** 1.61
- **Annual Standard Deviation:** 8%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from scipy.optimize import minimize

class AdaptiveAssetAllocation(bt.Strategy):
    params = (
        ('momentum_period', 126),  # 6-month momentum
        ('lookback_period', 60),  # 60-day historical data
        ('target_volatility', 0.08),
        ('rebalance_frequency', 5)  # Weekly rebalancing
    )

    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['momentum'] = bt.indicators.RateOfChange(
                period=self.params.momentum_period, plot=False)(d.close)

    def prenext(self):
        self.next()

    def next(self):
        if len(self) % self.params.rebalance_frequency == 0:
            # Select top 5 assets based on 6-month momentum
            top_assets = sorted(self.datas, key=lambda d: self.inds[d]['momentum'][0], reverse=True)[:5]

            # Calculate asset weights using minimum variance optimization
            rets = np.zeros((len(top_assets), self.params.lookback_period))
            for i, d in enumerate(top_assets):
                rets[i] = np.log(d.close.get(size=self.params.lookback_period))

            cov_matrix = np.cov(rets)

            def min_variance(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

            cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
            bounds = [(0, 1) for _ in range(len(top_assets))]
            initial_guess = np.array([1 / len(top_assets)] * len(top_assets))

            opt_result = minimize(min_variance, initial_guess, method='SLSQP', bounds=bounds, constraints=cons)
            weights = opt_result.x

            # Estimate overall portfolio volatility and rescale to target volatility
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            rescaled_weights = weights * (self.params.target_volatility / port_vol)

            # Execute trades
            for i, d in enumerate(self.datas):
                if d in top_assets:
                    self.order_target_percent(d, target=rescaled_weights[i])
                else:
                    self.order_target_percent(d, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add ETF data feeds here
    # cerebro.adddata(...)

    cerebro.addstrategy(AdaptiveAssetAllocation)
    cerebro.run()

```

Please note that you need to add the data feeds for the 10 ETFs representing the key asset classes.