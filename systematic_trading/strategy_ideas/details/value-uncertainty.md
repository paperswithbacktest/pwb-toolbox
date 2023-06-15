<div align="center">
  <h1>Value Uncertainty</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3299582)

## Trading rules

Trading rules of the strategy are:

- Calculate the Uncertainty of book-to-market (UNC) for the 500 largest NYSE stocks.
- Scale the uncertainty by their mean over the previous 12 months using equation 11 on page 13.
- Compute the expected book-to-market ratio using equations 7-10 on pages 11 and 12.
- Sort the stocks into 10 deciles.
- Long the top decile of stocks.
- Short the bottom decile of stocks.
- The strategy is value-weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1986-2016
- **Annual Return:** 12.01%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.55
- **Annual Standard Deviation:** 14.62%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class UncertaintyFactor(bt.Indicator):
    lines = ('uncertainty_factor',)

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.uncertainty_factor = ((self.dataclose - self.book_to_market.rolling(252).mean()) /
                                   self.book_to_market.rolling(252).std())

class ExpectedBMR(bt.Indicator):
    lines = ('expected_bmr',)

    def __init__(self):
        self.dataclose = self.datas[0].close
        # Calculation logic for expected_bmr

class Quantile(bt.Indicator):
    lines = ('quantile',)

    def __init__(self, n_groups):
        self.n_groups = n_groups
        self.quantile = pd.qcut(self.expected_bmr, self.n_groups,
                                labels=False, duplicates='drop') + 1

class ValueWeighted(bt.Strategy):
    params = (
        ('monthdays', [1]),
        ('n_groups', 10),
    )

    def __init__(self):
        self.book_to_market = self.datas[0].book_to_market
        self.book_value = self.datas[0].book_value
        self.market_value = self.datas[0].market_value
        self.uncertainty_factor = UncertaintyFactor(self.datas[0]).uncertainty_factor
        self.expected_bmr = ExpectedBMR(self.datas[0]).expected_bmr
        self.quantile = Quantile(self.params.n_groups)(self.expected_bmr).quantile
        self.weights = None

    def next(self):
        if not self.weights:
            self.weights = pd.Series(index=self.datas[0].close.index)

        # Select target quantiles for long and short positions
        top_quantile = self.quantile >= (self.params.n_groups - 1)
        bot_quantile = self.quantile <= 1

        # Calculate weights
        nsecurities = (~self.datas[0].close.isna()).sum()
        topw = 1 / top_quantile.sum()
        botw = -1 / bot_quantile.sum()

        self.weights[top_quantile] = topw / nsecurities
        self.weights[bot_quantile] = botw / nsecurities
        self.weights[~(top_quantile | bot_quantile)] = 0

        # Apply weights and rebalance
        self.order_target_percent(target=self.weights)

    def stop(self):
        self.rebalance()  # rebalance at end of backtest

    def rebalance(self):
        top_quantile = self.quantile >= (self.params.n_groups - 1)
        bot_quantile = self.quantile <= 1
        long_symbols = self.datas[0].close.columns[top_quantile]
        short_symbols = self.datas[0].close.columns[bot_quantile]

        # Close existing positions
        pos_dict = self.getpositions()
        for ticker in pos_dict:
            if ticker not in long_symbols and ticker not in short_symbols:
                self.close(self.getposition(self.getdatabyname(ticker)))

        # Open new positions
        long_weights = self.weights[top_quantile]
        short_weights = self.weights[bot_quantile]
        for ticker, weight in long_weights.iteritems():
            self.order_target_percent(data=self.getdatabyname(ticker), target=weight)

        for ticker, weight in short_weights.iteritems():
            self.order_target_percent(data=self.getdatabyname(ticker), target=weight)

```