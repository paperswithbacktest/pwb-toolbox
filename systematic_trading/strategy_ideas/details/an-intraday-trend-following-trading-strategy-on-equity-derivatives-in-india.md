<div align="center">
  <h1>An Intraday Trend-Following Trading Strategy on Equity Derivatives in India</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3342508)

## Trading rules

- Investment universe: Futures on stocks in the Nifty 50 Index
- Lookback period: 3 days
- Rebalancing period: 60 minutes
- Go long on positive momentum futures
- Go short on negative momentum futures
- Utilize risk-budgeting (simplified)
- Risk budgets: Proportional to absolute value of normalized indicator values
- Total risk allocation: 15% annualized for all indicators
- Target risk: 10%
- No weight optimization; weights scaled to achieve 15% risk and 100% exposure

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2010-2019
- **Annual Return:** 12.36%
- **Maximum Drawdown:** -13.44%
- **Sharpe Ratio:** 0.96
- **Annual Standard Deviation:** 12.81%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class IntradayMomentum(bt.Strategy):
    params = (
        ('lookback', 3),
        ('rebalancing_period', 60),
        ('total_risk_allocation', 0.15),
        ('target_risk', 0.10),
    )

    def __init__(self):
        self.momentum = {data: bt.indicators.Momentum(data, period=self.p.lookback) for data in self.datas}

    def next(self):
        if self.datetime.datetime(ago=0).minute % self.p.rebalancing_period == 0:
            positions = {data: self.getposition(data).size for data in self.datas}
            momentums = [self.momentum[data][0] for data in self.datas]
            normalized_momentum = np.array(momentums) / np.sum(np.abs(momentums))
            risk_budgets = np.abs(normalized_momentum)
            longs = [data for data in self.datas if self.momentum[data][0] > 0]
            shorts = [data for data in self.datas if self.momentum[data][0] < 0]
            weights = risk_budgets * self.p.total_risk_allocation / self.p.target_risk
            weights = weights / np.sum(weights) * 100

            for i, data in enumerate(self.datas):
                target_size = weights[i] * self.broker.getvalue() / data.close[0]
                self.order_target_size(data, target_size)

                if data in longs:
                    if positions[data] <= 0:
                        self.buy(data, exectype=bt.Order.Market, size=target_size)
                elif data in shorts:
                    if positions[data] >= 0:
                        self.sell(data, exectype=bt.Order.Market, size=target_size)
```

Please note that this code snippet is a simplified version of the strategy described and might not fully implement every aspect mentioned in the trading rules. For a more comprehensive implementation, you may need to adjust the code based on your specific data source and requirements.