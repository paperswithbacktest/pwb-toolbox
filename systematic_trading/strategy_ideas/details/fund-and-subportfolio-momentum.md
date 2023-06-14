<div align="center">
  <h1>Fund and Subportfolio Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3364124)

## Trading rules

- Investment universe: French’s 10 equally-weighted industrial sectors (use sector ETFs as proxy)
- Maximal lookback period: 18 months (180 combinations)
- Momentum measure: Trailing Exponential Average of Monthly Returns (EMAR)
- Monthly optimization: Determine positions for optimal number of subportfolios and lookback period based on best Sharpe ratio
- No long position in subportfolio if:
    - Trailing momentum doesn’t exceed cash
    - Momentum of excess return is not positive
- If subportfolios don’t beat cash, allocate proportional cash investment (e.g., 2/10 in cash for two subportfolios)
- Rebalance monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1937-2017
- **Annual Return:** 18.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.85
- **Annual Standard Deviation:** 22.12%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
from scipy.optimize import minimize

class EMARMomentum(bt.Strategy):
    params = (
        ('lookback', 18),
        ('rebalance_frequency', 21),
    )

    def __init__(self):
        self.etf_sectors = self.datas
        self.inds = dict()
        for d in self.etf_sectors:
            self.inds[d] = dict()
            self.inds[d]['emar'] = bt.indicators.EMA(d.close, period=self.params.lookback)

    def next(self):
        if self.datetime.date(0).day != 1:
            return

        emar_values = [self.inds[d]['emar'][0] for d in self.etf_sectors]
        excess_momentum = [emar - self.inds[d]['emar'][-1] for d in self.etf_sectors]
        positive_momentum = [emar > 0 for emar in excess_momentum]
        long_candidates = [self.etf_sectors[i] for i in range(len(self.etf_sectors)) if positive_momentum[i]]

        if not long_candidates:
            self.adjust_portfolio({}, self.etf_sectors)
            return

        opt_result = self.optimize_portfolio(long_candidates)
        target_weights = opt_result['weights']
        self.adjust_portfolio(target_weights, long_candidates)

    def optimize_portfolio(self, candidates):
        n = len(candidates)
        init_guess = np.array([1 / n] * n)
        bounds = [(0, 1) for _ in range(n)]

        def objective(weights, data):
            portfolio_returns = np.dot(weights, data)
            sharpe_ratio = np.mean(portfolio_returns) / np.std(portfolio_returns)
            return -sharpe_ratio

        def constraint(weights):
            return np.sum(weights) - 1

        cons = {'type': 'eq', 'fun': constraint}
        data = np.array([self.inds[d]['emar'].get(size=self.params.lookback) for d in candidates]).T
        opt_result = minimize(objective, init_guess, args=(data,), bounds=bounds, constraints=cons)
        return {'weights': opt_result.x}

    def adjust_portfolio(self, target_weights, long_candidates):
        current_holdings = [d for d, pos in zip(self.etf_sectors, self.positions) if pos]
        for d in current_holdings:
            if d not in long_candidates:
                self.sell(data=d)

        for i, d in enumerate(long_candidates):
            self.order_target_percent(data=d, target=target_weights[i])

cerebro = bt.Cerebro()
# Add sector ETF data feeds to cerebro
# Rebalance frequency set to 21 days (approx. 1 month)
cerebro.addstrategy(EMARMomentum, lookback=18, rebalance_frequency=21)
cerebro.run()
```

This code snippet assumes that you have already added your sector ETF data feeds to the `cerebro` instance. Please note that this code is not complete and may require additional modification and customization to work in your specific environment or with your data feeds.