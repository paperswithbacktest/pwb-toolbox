<div align="center">
  <h1>Out-of-Sample Exchange Rate Prediction: A Machine Learning Perspective</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3455713)

## Trading rules

- Investment universe: 14 countries’ currencies
    - Pre-1999: UK, Switzerland, Japan, Canada, Australia, New Zealand, Sweden, Norway, Denmark, Euro area, Germany, Italy, France, Netherlands
    - Post-1999: Euro replaces Germany, Italy, France, Netherlands
- Obtain data for country characteristics:
    - Inflation differential
    - Unemployment differential
    - Bill yield differential
    - Note yield differential
    - Bond yield differential
    - Dividend yield differential
    - Price-earnings differential
    - Market capitalization differential
    - Idiosyncratic volatility
    - Idiosyncratic skewness
- Global Variables:
    - Economic policy uncertainty
    - Monetary policy uncertainty
    - Geopolitical risk
    - Macro uncertainty
    - Global currency volatility
    - Global currency illiquidity
    - Global currency correlation
- Use panel predictive regression model (equation 3.6) with predictor x of length 80
- Compute predictor deviation from country-specific mean (equation 3.5)
- Estimate parameters using elastic net (equation 3.19)
- Predict out-of-sample change in exchange rate at time T+1
- Forecast currency excess return using government bill yield, bill yield for US, and predicted change in exchange rate
- Estimate variance-covariance matrix for currency excess returns with exponentially weighted moving average (decay parameter = 0.94)
- Determine weights using mean-variance optimization (objective function from equation 5.1)
- Rebalance strategy monthly

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1995-2017
- **Annual Return:** 10.72%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.55
- **Annual Standard Deviation:** 19.65%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet

class CarryStrategy(bt.Strategy):
    def __init__(self):
        self.pred_x = None
        self.weights = None

    def next(self):
        if self.datetime.date().month != self.datetime.date(-1).month:  # Rebalance monthly
            self.rebalance()

    def rebalance(self):
        country_data = self.get_country_data()
        global_vars = self.get_global_variables()
        predictor_dev = self.compute_predictor_deviation(country_data)
        params = self.estimate_parameters(predictor_dev, global_vars)
        excess_returns = self.forecast_excess_returns(country_data, global_vars, params)
        cov_matrix = self.estimate_covariance_matrix(excess_returns)
        self.weights = self.mean_variance_optimization(excess_returns, cov_matrix)
        self.adjust_positions()

    def get_country_data(self):
        # Implement data fetching for country characteristics
        pass

    def get_global_variables(self):
        # Implement data fetching for global variables
        pass

    def compute_predictor_deviation(self, country_data):
        # Compute predictor deviation from country-specific mean (equation 3.5)
        return country_data.subtract(country_data.mean(axis=0), axis=1)

    def estimate_parameters(self, predictor_dev, global_vars):
        # Estimate parameters using elastic net (equation 3.19)
        enet = ElasticNet()
        enet.fit(predictor_dev, global_vars)
        return enet.coef_

    def forecast_excess_returns(self, country_data, global_vars, params):
        # Predict out-of-sample change in exchange rate at time T+1 and
        # forecast currency excess return
        pass

    def estimate_covariance_matrix(self, excess_returns):
        # Estimate variance-covariance matrix for currency excess returns
        # with exponentially weighted moving average (decay parameter = 0.94)
        return excess_returns.ewm(alpha=0.06).cov()

    def mean_variance_optimization(self, excess_returns, cov_matrix):
        # Determine weights using mean-variance optimization (equation 5.1)
        pass

    def adjust_positions(self):
        # Adjust positions based on calculated weights
        pass

cerebro = bt.Cerebro()
# Add data feeds and strategy to cerebro
cerebro.adddata(...)
cerebro.addstrategy(CarryStrategy)
# Run backtest
results = cerebro.run()
```