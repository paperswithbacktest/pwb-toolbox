<div align="center">
  <h1>Economic Momentum and Currency Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2579666)

## Trading rules

- Investment universe: 19 countries’ currencies (vs. USD)
- Data collection: 8 fundamental variables
    - One-month interbank rate (computed using covered interest-rate parity)
    - Yield spread (short rates minus long rates)
    - Ten-year interest rate
    - Inflation
    - Trade balance (calculated as (Exports-Imports)/(Exports+Imports))
    - Industrial production (monthly growth rates)
    - Retail sales (monthly growth rates)
    - Unemployment (inverse of unemployment rate)
- Lookback periods: 1-60 months
- Portfolio rebalancing: End of each month
- Trend measures:
    1. Changes (or log changes) in variables
    2. Significance of linear time trends (t-statistic)
- Constructing strategies:
    - For each fundamental variable
    - For each trend measure
    - For each lookback period
- Currency ranking: According to strength of trend measures
- Weighting currencies: Based on cross-sectionally ranked signals
- Aggregate portfolios: Across variables, trend measures, and lookback periods
- Sub-strategy weighting: Inverse of volatility over the past three years (sum to one)
- Aggregate portfolio scaling: Factor of 5% divided by past realized volatility (volatility timing)

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1976-2014
- **Annual Return:** 6.15%
- **Maximum Drawdown:** -12.39%
- **Sharpe Ratio:** 1.1
- **Annual Standard Deviation:** 5.6%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
import statsmodels.api as sm

class EconomicMomentum(bt.Strategy):
    def __init__(self):
        self.lookback_periods = list(range(1, 61))
        self.rebalance_days = []
        self.aggregated_portfolio = None

    def prenext(self):
        if len(self.data) == 1:  # Start of the data
            self.rebalance_days.append(self.data.datetime.date(0))

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            self.rebalance_days.append(self.data.datetime.date(0))
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        sub_strategies = []
        for variable in self.data.get_variables():
            for lookback_period in self.lookback_periods:
                for trend_measure in [self.changes, self.linear_trend]:
                    sub_strategies.append(self.construct_strategy(variable, lookback_period, trend_measure))

        weights = self.calculate_weights(sub_strategies)
        self.aggregated_portfolio = self.aggregate_portfolios(sub_strategies, weights)
        self.order_target_percent(self.aggregated_portfolio, target=0.05 / self.aggregated_portfolio.volatility)

    def changes(self, data, lookback_period):
        return data.diff(lookback_period).dropna()

    def linear_trend(self, data, lookback_period):
        trends = []
        for i in range(len(data) - lookback_period + 1):
            y = data.iloc[i:i + lookback_period].values
            x = np.arange(lookback_period)
            x = sm.add_constant(x)
            model = sm.OLS(y, x).fit()
            trends.append(model.tvalues[1])
        return pd.Series(trends, index=data.index[-len(trends):])

    def construct_strategy(self, variable, lookback_period, trend_measure):
        trend_data = trend_measure(variable, lookback_period)
        ranked_data = trend_data.rank()
        return ranked_data / ranked_data.sum()

    def calculate_weights(self, sub_strategies):
        weights = []
        for sub_strategy in sub_strategies:
            volatility = sub_strategy.pct_change().rolling(window=36 * 30).std().iloc[-1]
            weights.append(1 / volatility)
        return [w / sum(weights) for w in weights]

    def aggregate_portfolios(self, sub_strategies, weights):
        weighted_sub_strategies = [sub_strategy * weight for sub_strategy, weight in zip(sub_strategies, weights)]
        return sum(weighted_sub_strategies)

cerebro = bt.Cerebro()
data = bt.feeds.YourDataFeed()  # Replace with your custom data feed
cerebro.adddata(data)
cerebro.addstrategy(EconomicMomentum)
cerebro.broker.setcash(1000000.0)
initial_value = cerebro.broker.getvalue()
print('Starting Portfolio Value: %.2f' % initial_value)
cerebro.run()
final_value = cerebro.broker.getvalue()
print('Final Portfolio Value: %.2f' % final_value)
```