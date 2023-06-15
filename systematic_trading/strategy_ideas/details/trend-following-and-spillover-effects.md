<div align="center">
  <h1>Trend-Following and Spillover Effects</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3473657)

## Trading rules

- Investment universe includes currency forwards, equity indices, and index futures.
- Consider relationships between asset classes: Bonds have negative effect on FX and positive effect on Equities; Equities have negative effect on Bonds and negative effect on FX; FX has positive effect on Equities and positive effect on Bonds.
- Pick lookback period from 3 to 4 years.
- Signal is defined as the signum function of the cumulative returns for the asset that has a spillover on another from date t minus the lookback period to date t.
- Allocate one-third of the overall risk budget to each asset class.
- Equal risk contribution within asset classes.
- Weights are obtained from a maximization of the sum of natural logarithms of weights in the absolute values.
- Rebalance weekly.
- Form summary strategy from 6 strategies: spillover of bonds to FX and equities, spillover of equities on FX and bonds, and spillover of FX to bonds and equities.

## Statistics

- **Markets Traded:** Bonds, currencies, equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1999-2019
- **Annual Return:** 3.2
- **Maximum Drawdown:** -12.3
- **Sharpe Ratio:** 0.67
- **Annual Standard Deviation:** 4.8

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class CrossAssetStrategy(bt.Strategy):

    params = (
        ('lookback', 3*252),  # Assuming 252 trading days per year
        ('rebalance_days', 5),  # Rebalance weekly
        ('risk_budget', 1/3),  # One third of overall risk budget
    )

    def __init__(self):
        self.data_close = self.datas[0].close  # Assuming this is the equity index
        self.fx_forward = self.datas[1].close  # Assuming this is the FX forward
        self.index_future = self.datas[2].close  # Assuming this is the index future (representing bonds)

        self.lookback_returns = {data: [] for data in self.datas}
        self.cumulative_signals = {data: [] for data in self.datas}
        self.weights = {data: self.p.risk_budget for data in self.datas}

    def next(self):
        # Calculate lookback returns and signal for each asset
        for data in self.datas:
            if len(data) < self.p.lookback:
                continue
            returns = (data.close[0] - data.close[-self.p.lookback]) / data.close[-self.p.lookback]
            self.lookback_returns[data].append(returns)
            self.cumulative_signals[data].append(np.sign(self.lookback_returns[data][-1]))

        # Skip if we haven't reached the lookback period yet
        if len(self.data_close) < self.p.lookback:
            return

        # Rebalance the portfolio every week
        if len(self.data_close) % self.p.rebalance_days == 0:
            # Update the weights based on the signals and asset correlations
            self.weights[self.data_close] = np.log(np.abs(self.cumulative_signals[self.data_close][-1] - self.cumulative_signals[self.index_future][-1]))
            self.weights[self.fx_forward] = np.log(np.abs(self.cumulative_signals[self.fx_forward][-1] - self.cumulative_signals[self.data_close][-1]))
            self.weights[self.index_future] = np.log(np.abs(self.cumulative_signals[self.index_future][-1] - self.cumulative_signals[self.fx_forward][-1]))

            # Normalize the weights to sum to the risk budget
            total_weight = sum(self.weights.values())
            for data in self.weights:
                self.weights[data] /= total_weight
                self.weights[data] *= self.p.risk_budget

            # Rebalance the portfolio
            for data, weight in self.weights.items():
                self.order_target_percent(data, target=weight)
```