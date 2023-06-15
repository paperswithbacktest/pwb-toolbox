<div align="center">
  <h1>Return Predictability and Market-Timing: A One-Month Model</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3050254)

## Trading rules

- Investment universe consists of S&P 500.
- Consider 15 forecasting variables for predicting the one-month ahead equity risk premium.
- Normalize all predictors by dividing by their standard deviations using a backward-looking window of 500 days.
- Use a weighted least square method (WLS) with a decay factor of 0.99 at monthly frequency to estimate the WLS specification.
- Incorporate a bidirectional stepwise procedure in the WLS specification.
- Variables are chosen based on the Akaike Information Criterion.
- Obtain model parameters at the end of month t-1 and hold them constant for month t.
- Use updated return predictors along with fixed model parameters to produce one-month equity risk premium forecasts on a daily frequency.
- Re-estimate the model using an expanding window each month to obtain new parameter values used for the next month’s equity premium forecasts.
- Amount invested in the market is determined by transforming the raw equity premium forecasts.
- Equity premium forecasts are scaled by the inverse of the root mean square error (RMSE) and multiplied by five to produce the percentual amount invested in the S&P 500.
- Invest the rest in Treasury-bills.
- If the equity premium forecast is negative, invest everything in Treasury-bills.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2003-2017
- **Annual Return:** 16.6%
- **Maximum Drawdown:** -20.3%
- **Sharpe Ratio:** 0.76
- **Annual Standard Deviation:** 16.6%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import WLS
from sklearn.preprocessing import StandardScaler

class WLSForecastingStrategy(bt.Strategy):

    params = (
        ('scale_factor', 5),
        ('window_length', 500),
        ('decay_factor', 0.99),
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.forecasting_vars = [self.datas[i].close for i in range(1, 16)]
        self.scaler = StandardScaler()
        self.params_history = []

    def next(self):
        if len(self.data) < self.p.window_length:
            return

        # Get the past 500 days of forecasting variable data
        data_window = [var.get(size=self.p.window_length) for var in self.forecasting_vars]
        data_window = np.array(data_window).T

        # Scale the data
        data_window = self.scaler.fit_transform(data_window)

        # WLS estimation with a decay factor
        weights = np.power(self.p.decay_factor, np.arange(self.p.window_length)[::-1])
        wls = WLS(self.data_close.get(size=self.p.window_length), data_window, weights=weights)

        # Implement a bidirectional stepwise procedure
        # This is just a placeholder. The actual implementation will depend on your specific criteria.
        # You will need to use AIC to select the best model.
        # This may involve writing additional helper functions.
        # For example:
        # wls = self.bidirectional_stepwise_selection(wls)

        # Fit the model
        results = wls.fit()

        # Store the params for next month forecast
        self.params_history.append(results.params)

        # If we have enough data for next month
        if len(self.params_history) > 1:

            # Get the latest parameters
            params_t_1 = self.params_history[-2]

            # Generate the equity premium forecast for next month
            equity_premium_forecast = np.dot(params_t_1, data_window[-1])

            if equity_premium_forecast < 0:
                # If the equity premium forecast is negative, invest everything in Treasury-bills
                self.order_target_percent(self.datas[0], 0)
            else:
                # Compute the investment based on equity premium forecast
                # The investment is scaled by the inverse of the RMSE and multiplied by a scale factor
                rmse = np.sqrt(results.mse_resid)
                investment = equity_premium_forecast / rmse * self.p.scale_factor
                self.order_target_percent(self.datas[0], investment)
```