<div align="center">
  <h1>Strategies Can Be Expensive Too! The Value Spread and Asset Allocation in Global Equity Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332931)

## Trading rules

- Investment universe consists of 42 country exchange-traded funds.
- 120 individual international equity strategies are constructed based on 9 major categories of anomalies.
- Anomaly portfolios are formed using ETFs sorted on anomaly-related return-predicting variables.
- 25th and 75th percentiles are determined to create long and short portfolios.
- Equal-weighted portfolios are built and monthly rebalanced to create long-short zero-investment portfolios.
- Long positions are taken in portfolios with higher expected returns and short positions in portfolios with lower expected returns.
- Value spread is defined as the difference between valuation ratios of the long and short sides of the zero-investment anomaly portfolio.
- EBITDA-to-enterprise value ratio (EBEV) is used as a value measure.
- Value spread is calculated using a weighted sum of EBEVs for long and short sides.
- 12 strategies with the highest value spreads are selected for a monthly equally-weighted portfolio.
- Portfolio is rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1996-2017
- **Annual Return:** 5.91
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.93
- **Annual Standard Deviation:** 6.37

## Python code

### Backtrader

```python
# Import necessary modules
import backtrader as bt
import pandas as pd

class TradingStrategy(bt.Strategy):
    def __init__(self):
        self.long_portfolios = {} # Dictionary to store long portfolios
        self.short_portfolios = {} # Dictionary to store short portfolios
        self.equal_weight = 1 / len(anomaly_categories) # Equal weight for each category
        self.value_spread = 0 # Initialize value spread
        self.top_strategies = [] # List to store top strategies

        # Create universe of 42 country exchange traded funds
        self.universe = ['ETF1', 'ETF2', ..., 'ETF42']

        # Create international equity strategies based on 9 major categories of anomalies
        self.anomaly_categories = ['anomaly1', 'anomaly2', ..., 'anomaly9']
        for anomaly in self.anomaly_categories:
            self.long_portfolios[anomaly] = []
            self.short_portfolios[anomaly] = []

        # Sort ETFs on anomaly-related return-predicting variables to form anomaly portfolios
        self.anomaly_portfolios = {}
        for anomaly in self.anomaly_categories:
            self.anomaly_portfolios[anomaly] = self.sort_efts_on_anomaly_related_return_predicting_variables(anomaly)

        # Determine 25th and 75th percentiles to create long and short portfolios
        self.long_short_portfolios = {}
        for anomaly in self.anomaly_categories:
            self.long_short_portfolios[anomaly] = self.create_long_short_portfolios(anomaly)

        # Create equal-weighted portfolios and monthly rebalanced to create long-short zero-investment portfolios
        for anomaly in self.anomaly_categories:
            anomaly_long = self.long_short_portfolios[anomaly]['long']
            anomaly_short = self.long_short_portfolios[anomaly]['short']
            self.long_portfolios[anomaly] = bt.Portfolio(anomaly_long, multiplier=self.equal_weight)
            self.short_portfolios[anomaly] = bt.Portfolio(anomaly_short, multiplier=self.equal_weight)

        # Take long positions in portfolios with higher expected returns and short positions in portfolios with lower expected returns
        self.leverage = 1 / len(self.anomaly_categories) # Equal leverage for each strategy
        self.strategies = {} # Dictionary to store strategies for each anomaly category
        for anomaly in self.anomaly_categories:
            long_pos = self.long_portfolios[anomaly]
            short_pos = self.short_portfolios[anomaly]
            strategy = self.take_long_short_positions(long_pos, short_pos)
            self.strategies[anomaly] = strategy

        # Define EBITDA-to-enterprise value ratio (EBEV) as a value measure
        self.EBEV = self.calculate_EBEV()

        # Calculate value spread using a weighted sum of EBEVs for long and short sides
        for anomaly in self.anomaly_categories:
            long_EBEV = self.calculate_EBEV(anomaly_long)
            short_EBEV = self.calculate_EBEV(anomaly_short)
            self.value_spread += (long_EBEV - short_EBEV) * self.equal_weight

        # Select top 12 strategies based on value spreads
        self.top_strategies = self.select_top_strategies(self.strategies)

    def next(self):
        # Rebalance portfolio monthly based on selected strategies
        if self.datas[0].datetime.date().day == 1:
            self.rebalance()

    def rebalance(self):
        for anomaly in self.anomaly_categories:
            # Check if selected strategy is in top 12 strategies
            if self.strategies[anomaly] in self.top_strategies:
                self.order_target_percent(self.strategies[anomaly], self.leverage)
            else:
                self.order_target_percent(self.strategies[anomaly], 0)

    def sort_efts_on_anomaly_related_return_predicting_variables(self, anomaly):
        # Sort ETFs based on anomaly-related return-predicting variables
        # Returns a list of sorted ETFs
        pass

    def create_long_short_portfolios(self, anomaly):
        # Determine 25th and 75th percentiles and create long and short portfolios
        # Returns a dictionary with 'long' and 'short' keys holding lists of ETFs
        pass

    def take_long_short_positions(self, long_pos, short_pos):
        # Take long positions in portfolios with higher expected returns and short positions in portfolios with lower expected returns
        # Returns the strategy object
        pass

    def calculate_EBEV(self, portfolio):
        # Calculate EBITDA-to-enterprise value ratio (EBEV) for given portfolio
        # If no portfolio is given, calculate for entire universe
        pass

    def select_top_strategies(self, strategies):
        # Select top 12 strategies based on value spreads
        # Returns a list of strategy objects
        pass
```