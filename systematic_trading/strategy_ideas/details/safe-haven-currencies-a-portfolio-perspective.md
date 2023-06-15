<div align="center">
  <h1>Safe Haven Currencies: A Portfolio Perspective</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2606662)

## Trading rules

- Borrow for one month at the lowest interest rate currency and invest at the highest interest rate currency in the Carry Trade strategy
- Observe the difference between realized exchange rate and fundamental equilibrium level for the PPP strategy
- Estimate fundamental equilibrium level for each exchange rate (28 pairs) using a regression equation and price level differences
- Use 1980-1990 as the initial sample for calculating the first fundamental equilibrium level, followed by recursive out-of-sample estimates
- Bet on reversion to the fundamental value on a one-month time horizon
- Borrow in the most overvalued currency and invest in the most undervalued currency for the PPP strategy
- Identify crisis periods when the VIX index is more than one standard deviation above its historical average since 1990
- Implement Carry Trade strategy in calm periods and PPP strategy in crisis periods

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1990-2008
- **Annual Return:** 8.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.87
- **Annual Standard Deviation:** 4.97%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class CarryTradeAndPPPStrategy(bt.Strategy):
    def __init__(self):
        self.vix_data = self.get_vix_data()
        self.regression_model = LinearRegression()
        self.initial_sample = self.get_initial_sample()

    def next(self):
        # Calculate VIX index standard deviation
        vix_std = self.vix_data.loc[:self.datas[0].datetime.date()].std()

        # Identify crisis periods
        is_crisis_period = self.vix_data.iloc[-1] > (vix_std + self.vix_data.mean())

        if is_crisis_period:
            self.execute_ppp_strategy()
        else:
            self.execute_carry_trade_strategy()

    def execute_carry_trade_strategy(self):
        interest_rates = self.get_interest_rates()
        min_rate_currency = interest_rates.idxmin()
        max_rate_currency = interest_rates.idxmax()

        # Borrow in the currency with the lowest interest rate
        self.sell(data=self.getdatabyname(min_rate_currency))

        # Invest in the currency with the highest interest rate
        self.buy(data=self.getdatabyname(max_rate_currency))

    def execute_ppp_strategy(self):
        fundamental_eq_levels = self.calculate_fundamental_equilibrium_levels()
        exchange_rate_diff = self.get_exchange_rate_diff(fundamental_eq_levels)
        most_overvalued_currency = exchange_rate_diff.idxmax()
        most_undervalued_currency = exchange_rate_diff.idxmin()

        # Borrow in the most overvalued currency
        self.sell(data=self.getdatabyname(most_overvalued_currency))

        # Invest in the most undervalued currency
        self.buy(data=self.getdatabyname(most_undervalued_currency))

    def get_vix_data(self):
        # Load VIX data
        return pd.read_csv('vix_data.csv', index_col=0, parse_dates=True)

    def get_interest_rates(self):
        # Load interest rate data
        return pd.read_csv('interest_rates.csv', index_col=0, parse_dates=True).iloc[-1]

    def get_initial_sample(self):
        # Load initial sample data (1980-1990)
        return pd.read_csv('initial_sample.csv', index_col=0, parse_dates=True)

    def calculate_fundamental_equilibrium_levels(self):
        # Calculate fundamental equilibrium levels using regression
        fundamental_eq_levels = {}
        for pair in self.get_currency_pairs():
            price_level_diff = self.get_price_level_difference(pair)
            self.regression_model.fit(price_level_diff, self.initial_sample[pair])
            fundamental_eq_level = self.regression_model.predict(price_level_diff)
            fundamental_eq_levels[pair] = fundamental_eq_level
        return fundamental_eq_levels

    def get_currency_pairs(self):
        # Get list of currency pairs
        return self.initial_sample.columns

    def get_price_level_difference(self, pair):
        # Calculate price level differences for each currency pair
        return self.initial_sample[pair].diff().dropna()

    def get_exchange_rate_diff(self, fundamental_eq_levels):
        # Calculate difference between realized exchange rate and fundamental equilibrium level
        exchange_rate_diff = {}
        for pair, fundamental_eq_level in fundamental_eq_levels.items():
            realized_exchange_rate = self.getdatabyname(pair).close[0]
            diff = realized_exchange_rate - fundamental_eq_level
            exchange_rate_diff[pair] = diff
        return exchange_rate_diff
```