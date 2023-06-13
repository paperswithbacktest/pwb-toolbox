<div align="center">
  <h1>Deviations from Put-Call Parity and Stock Return Predictability</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968237)

## Trading rules

Here are the trading rules for the described strategy:

- The investment universe is stocks with liquid and actively traded options.
- Implied volatility for each stock is computed weekly from Wednesday closing prices.
- The volatility spread is calculated as the weighted average spread between calls and puts valid pairs across strikes and maturities.
- Every Wednesday, firms are sorted independently into five categories based on the change in the volatility spread between Tuesday and Wednesday, and five categories based on the level of the volatility spread on Tuesday.
- This creates a total of 25 portfolios.
- On Thursday morning, a long/short hedge portfolio is created by buying stocks with high Tuesday volatility spread and high Tuesday to Wednesday volatility spread change, and selling stocks with low Tuesday volatility spread and low Tuesday to Wednesday volatility spread change.
- The stocks in the portfolio are value-weighted.
- The portfolio is rebalanced weekly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1996-2005
- **Annual Return:** 29.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.23
- **Annual Standard Deviation:** 20.86%

## Python code

### Backtrader

```python
import backtrader as bt

class VolatilitySpread(bt.Strategy):
    def __init__(self):
        self.stocks = self.datas[0]

    def next(self):
        if self.datetime.date(0).weekday() == 2:
            self.iv = self.compute_implied_volatility()

        if self.datetime.date(0).weekday() == 3:
            long_stocks, short_stocks = self.select_stocks()
            self.rebalance_portfolio(long_stocks, short_stocks)

    def compute_implied_volatility(self):
        # Compute implied volatility from Wednesday closing prices
        # For each stock in investment universe
        return iv

    def select_stocks(self):
        # Sort stocks into 25 portfolios based on volatility spread
        # Select long and short stocks based on Tuesday and Wednesday volatility spread change
        return long_stocks, short_stocks

    def rebalance_portfolio(self, long_stocks, short_stocks):
        # Create value-weighted portfolio of selected stocks
        # Rebalance portfolio weekly
        pass
```

Note: This code only outlines the general structure of the strategy and does not include the specific implementation details for computing implied volatility or selecting stocks.