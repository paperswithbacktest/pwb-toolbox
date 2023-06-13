<div align="center">
  <h1>Diversification Effect of Standard and Optimized Carry Trades</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2619678)

## Trading rules

- Use USD as the domestic currency
- Invest in CHF, EUR, JPY, GBP, AUD, CAD, NOK, SEK, SGD, and NZD
- Compute expected excess return monthly for each currency (currency interest rate - U.S. risk-free rate)
- Re-estimate daily covariance matrix monthly using the last 250 observations
- Apply mean-variance methodology to determine optimal long/short weights for each currency
- Set an annual target excess return of 5% for calculations
- Rebalance portfolio on a monthly basis

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1990-2012
- **Annual Return:** 10.88%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.99
- **Annual Standard Deviation:** 6.97%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd

class MeanVarianceOptimization(bt.Strategy):
    params = (
        ('target_excess_return', 0.05),
        ('rebalance_days', 30),
    )

    def __init__(self):
        self.currencies = ['CHF', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'NOK', 'SEK', 'SGD', 'NZD']
        self.data_names = [f"{cur}USD" for cur in self.currencies]
        self.datas_dict = {name: d for name, d in zip(self.data_names, self.datas)}
        self.days_since_rebalance = 0

    def next(self):
        self.days_since_rebalance += 1
        if self.days_since_rebalance >= self.params.rebalance_days:
            self.rebalance_portfolio()
            self.days_since_rebalance = 0

    def rebalance_portfolio(self):
        hist_data = pd.DataFrame()
        for name in self.data_names:
            hist_data[name] = self.datas_dict[name].get(size=250)

        excess_returns = self.compute_excess_returns(hist_data)
        cov_matrix = hist_data.pct_change().cov()
        optimal_weights = self.mean_variance_optimization(excess_returns, cov_matrix)

        for i, name in enumerate(self.data_names):
            self.order_target_percent(self.datas_dict[name], target=optimal_weights[i])

    def compute_excess_returns(self, hist_data):
        excess_returns = []
        for name in self.data_names:
            currency_interest_rate = self.get_currency_interest_rate(name)
            us_risk_free_rate = self.get_us_risk_free_rate()
            excess_return = currency_interest_rate - us_risk_free_rate
            excess_returns.append(excess_return)

        return excess_returns

    def get_currency_interest_rate(self, name):
        # Implement a method to get the currency interest rate
        pass

    def get_us_risk_free_rate(self):
        # Implement a method to get the U.S. risk-free rate
        pass

    def mean_variance_optimization(self, excess_returns, cov_matrix):
        target_excess_return = self.params.target_excess_return / 12
        inv_cov_matrix = np.linalg.inv(cov_matrix.values)
        ones = np.ones(len(excess_returns))
        weights = np.dot(inv_cov_matrix, excess_returns - target_excess_return * ones)
        weights /= np.dot(ones, np.dot(inv_cov_matrix, excess_returns - target_excess_return * ones))

        return weights

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MeanVarianceOptimization)

    for cur in ['CHF', 'EUR', 'JPY', 'GBP', 'AUD', 'CAD', 'NOK', 'SEK', 'SGD', 'NZD']:
        data = bt.feeds.YourDataFeed(dataname=f"{cur}USD")
        cerebro.adddata(data)

    cerebro.broker.setcash(100000.0)
    cerebro.run()
```

Please note that you will need to replace `bt.feeds.YourDataFeed` with the actual data feed class you are using, and implement the methods `get_currency_interest_rate` and `get_us_risk_free_rate` to fetch the required rates.