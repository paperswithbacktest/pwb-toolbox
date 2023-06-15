<div align="center">
  <h1>Time-Varying Sharpe Ratios and Market Timing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1938613)

## Trading rules

- Estimate conditional Sharpe ratio using 10-year rolling regression
- Compare the conditional Sharpe ratio to a fixed threshold (0.2)
- Each month, use two regression equations:
    - Estimate mean with one equation
    - Estimate volatility with the other equation
- Independent variables: dividend + repurchase yields (other predictors can be used)
- Calculate predicted Sharpe ratio using estimated ratios
- If estimated Sharpe ratio > threshold (0.2), invest in stock market
- If estimated Sharpe ratio < threshold (0.2), invest in risk-free asset

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1953-2010
- **Annual Return:** 14.18%
- **Maximum Drawdown:** 1.111%
- **Sharpe Ratio:** 0.66
- **Annual Standard Deviation:** 15.38%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression

class MarketTimingStrategy(bt.Strategy):
    params = (('threshold', 0.2),)

    def __init__(self):
        self.rolling_window = 120  # 10 years * 12 months

    def next(self):
        # Get historical data for the rolling window
        close_prices = np.array(self.data.close.get(size=self.rolling_window))
        dividend_yields = np.array(self.data.dividend_yields.get(size=self.rolling_window))
        repurchase_yields = np.array(self.data.repurchase_yields.get(size=self.rolling_window))

        # Calculate returns, assuming risk-free rate is zero
        returns = np.diff(close_prices) / close_prices[:-1]

        # Calculate excess returns
        excess_returns = returns

        # Calculate the independent variables (predictors)
        predictors = dividend_yields[:-1] + repurchase_yields[:-1]

        # Fit the regression models for mean and volatility estimation
        mean_model = LinearRegression().fit(predictors.reshape(-1, 1), excess_returns)
        vol_model = LinearRegression().fit(predictors.reshape(-1, 1), np.square(excess_returns))

        # Estimate the mean and volatility
        mean_estimate = mean_model.predict(predictors[-1].reshape(-1, 1))
        vol_estimate = np.sqrt(vol_model.predict(predictors[-1].reshape(-1, 1)))

        # Calculate the estimated conditional Sharpe ratio
        estimated_sharpe_ratio = mean_estimate / vol_estimate

        # Implement the investment strategy
        if estimated_sharpe_ratio > self.params.threshold:
            self.order_target_percent(self.data, target=1.0)
        else:
            self.order_target_percent(self.data, target=0.0)
```