<div align="center">
  <h1>Using Option-Implied Information to Improve Currency Carry Trade Profits</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2851543)

## Trading rules

- Investment universe consists of G-10 currencies
- Simple equal-weighted carry trade strategy is created by taking short and long positions in one currency at the end of each month
- Ranking of currencies is based on their realizable interest rate differentials inferred from spot and forward rates
- Three predictors are used to time the carry trade strategy:
    - Monthly change in average currency volatility, calculated as the standard deviation of daily exchange rate percentage changes against the U.S. dollar over a month
    - Monthly percentage changes in the MSCI world equity price index, useful as a predictor for payoffs from short legs of carry trades
    - Monthly percentage changes in the Raw Industrials Spot Commodity Index, useful as a predictor of long leg carry trade payoffs
- Two regression equations are used to predict the carry trade strategy’s long and short legs
- Long leg prediction uses monthly change in commodity index 3 months ago and change in average currency volatility 3 months ago as independent variables
- Short leg prediction uses monthly change in equity index 3 months ago and change in average currency volatility 2 months ago as independent variables
- Trading decision is based on one-step-ahead prediction of carry trade payoffs
- Carry trade is executed if predicted payoff is positive; otherwise, it is avoided
- Trading decision is applied to each leg of the carry trade.

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1985-2011
- **Annual Return:** 9.16%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.01
- **Annual Standard Deviation:** 9.07%

## Python code

### Backtrader

```python
# Import necessary packages
import backtrader as bt
import pandas as pd

# Define the G-10 currencies investment universe
g10 = ['USD', 'EUR', 'JPY', 'GBP', 'CAD', 'AUD', 'CHF', 'NZD', 'NOK', 'SEK']

class CarryTradeStrategy(bt.Strategy):

    def __init__(self):

        # Set the initial ranking of the currencies based on their interest rate differentials
        self.currencies = g10
        self.ranking = pd.Series(index=self.currencies, data=[0]*len(self.currencies))

        # Define variables to store predictors used for timing
        self.currency_volatility = {}
        self.eq_index = {}
        self.commodity_index = {}

        # Define variables to store regression coefficients and intercepts
        self.long_coeffs = {}
        self.long_intercept = {}
        self.short_coeffs = {}
        self.short_intercept = {}

        # Define variables to store historical data for each currency
        self.historical_data = {}

        # Define the time period for the predictors
        self.predictor_lookback = 3

    def next(self):

        # Update the ranking of currencies based on their interest rate differentials
        for currency in self.currencies:
            # code for retrieving interest rate data omitted for brevity

        self.ranking = self.ranking.rank(ascending=False, method='dense')

        # Calculate the predictors for each currency
        for currency in self.currencies:
            # code for retrieving historical data omitted for brevity

            # Calculate monthly change in average currency volatility using daily exchange rate percentage changes
            volatility = self.historical_data[currency]['Close'].pct_change().rolling(window=21).std().iloc[-1] * (252 ** 0.5)
            self.currency_volatility[currency] = volatility

            # Retrieve the monthly percentage change in the MSCI world equity price index
            eq_index_change = get_monthly_change('msci_world_equity_index')
            self.eq_index[currency] = eq_index_change

            # Retrieve the monthly percentage change in the Raw Industrials Spot Commodity Index
            commodity_index_change = get_monthly_change('raw_industrials_spot_commodity_index')
            self.commodity_index[currency] = commodity_index_change

        # Fit regression models for predicting long and short legs of the carry trade
        self.long_coeffs, self.long_intercept = self._fit_regression('long')
        self.short_coeffs, self.short_intercept = self._fit_regression('short')

        # Calculate the predicted payoffs for each currency
        predicted_payoffs = pd.Series(index=self.currencies)
        for currency in self.currencies:
            # Calculate predicted payoff for long leg of carry trade
            long_payoff = self.long_intercept[currency] + self.long_coeffs[currency]['commodity_index_change'] * self.commodity_index[currency] + self.long_coeffs[currency]['currency_volatility_change'] * self.currency_volatility[currency]

            # Calculate predicted payoff for short leg of carry trade
            short_payoff = self.short_intercept[currency] + self.short_coeffs[currency]['equity_index_change'] * self.eq_index[currency] + self.short_coeffs[currency]['currency_volatility_change'] * self.currency_volatility[currency]

            # Combine predicted payoffs for long and short legs
            predicted_payoff = long_payoff - short_payoff

            predicted_payoffs[currency] = predicted_payoff

        # Execute the carry trade for each currency with a positive predicted payoff
        for currency in self.currencies:
            if predicted_payoffs[currency] > 0:
                # Execute the carry trade for the long leg
                long_position = 0.5 / len(self.currencies)
                self.buy(data=self.getdatabyname(currency), size=long_position)

                # Execute the carry trade for the short leg
                short_position = -0.5 / len(self.currencies)
                self.sell(data=self.getdatabyname(currency), size=short_position)

    def _fit_regression(self, leg):
        coeffs = {}
        intercept = {}
        for currency in self.currencies:
            if leg == 'long':
                # Calculate independent variables for long leg regression
                commodity_index_change = self.commodity_index[currency].shift(self.predictor_lookback).dropna()
                currency_volatility_change = self.currency_volatility[currency].shift(self.predictor_lookback).dropna()
                dependent_variable = self.historical_data[currency]['Close'].pct_change(periods=self.predictor_lookback + 1).shift(-self.predictor_lookback - 1).dropna()
            else:
                # Calculate independent variables for short leg regression
                equity_index_change = self.eq_index[currency].shift(self.predictor_lookback).dropna()
                currency_volatility_change = self.currency_volatility[currency].shift(self.predictor_lookback - 1).dropna()
                dependent_variable = self.historical_data[currency]['Close'].pct_change(periods=self.predictor_lookback + 1).shift(-self.predictor_lookback - 1).dropna().apply(lambda x: -x)

            # Fit linear regression model with independent and dependent variables
            X = pd.concat([commodity_index_change, currency_volatility_change], axis=1)
            model = LinearRegression().fit(X, dependent_variable)
            coeffs[currency] = {'commodity_index_change': model.coef_[0], 'currency_volatility_change': model.coef_[1]}
            intercept[currency] = model.intercept_

        return coeffs, intercept
```