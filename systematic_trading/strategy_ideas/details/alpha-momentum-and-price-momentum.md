<div align="center">
  <h1>Alpha Momentum and Price Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287848)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ domestic primary stocks priced over $1
- Exclude closed-end funds, REITs, unit trusts, ADRs, and foreign stocks
- Select 10% largest stocks by market capitalization
- Define strategy as top-minus-bottom decile portfolio based on monthly ranking of past 12-month residual returns (excluding most recent month), standardized by standard deviation of residual returns in the same period
- Estimate residual returns for all stocks each month using a 36-month regression model
- Use Fama and French three factors as independent variables in regression model for eligible stocks
- Equally weight and rebalance portfolio monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1926-2009
- **Annual Return:** 9.18%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.34
- **Annual Standard Deviation:** 15.27%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
from sklearn.linear_model import LinearRegression

class ResidualMomentum(bt.Strategy):
    params = (
        ('lookback', 12),
        ('exclude_recent', 1),
        ('rebalance_period', 21),
        ('num_stocks', 0.1),
    )

    def __init__(self):
        self.counter = 0
        self.ff_factors = get_fama_french_factors()  # Implement function to get Fama-French factors data

    def next(self):
        if self.counter % self.params.rebalance_period == 0:
            eligible_stocks = self.get_eligible_stocks()
            residual_returns = self.calculate_residual_returns(eligible_stocks)
            selected_stocks = self.select_stocks(residual_returns)
            self.adjust_portfolio(selected_stocks)
        self.counter += 1

    def get_eligible_stocks(self):
        # Implement function to get eligible stocks from NYSE, AMEX, and NASDAQ, filtering out excluded types and priced over $1
        pass

    def calculate_residual_returns(self, eligible_stocks):
        residual_returns = {}
        for stock in eligible_stocks:
            stock_data = self.get_stock_data(stock)
            stock_returns = self.calculate_stock_returns(stock_data)
            residual_return = self.calculate_stock_residual_return(stock_returns)
            residual_returns[stock] = residual_return
        return residual_returns

    def select_stocks(self, residual_returns):
        num_stocks = int(len(residual_returns) * self.params.num_stocks)
        sorted_stocks = sorted(residual_returns, key=residual_returns.get, reverse=True)
        return sorted_stocks[:num_stocks]

    def adjust_portfolio(self, selected_stocks):
        weight = 1.0 / len(selected_stocks)
        for stock in selected_stocks:
            self.order_target_percent(stock, target=weight)

    def get_stock_data(self, stock):
        # Implement function to get stock data needed for regression analysis and stock returns calculation
        pass

    def calculate_stock_returns(self, stock_data):
        stock_data['return'] = stock_data['close'].pct_change()
        return stock_data

    def calculate_stock_residual_return(self, stock_returns):
        lookback_range = self.params.lookback - self.params.exclude_recent
        X = self.ff_factors.iloc[-lookback_range:]
        y = stock_returns['return'].iloc[-lookback_range:]
        model = LinearRegression()
        model.fit(X, y)
        residuals = y - model.predict(X)
        return residuals.mean() / residuals.std()
```

This code outlines the main structure of the Residual Momentum strategy using Backtrader. You will need to implement additional functions such as `get_fama_french_factors()`, `get_eligible_stocks()`, and `get_stock_data()`, which are specific to your data sources for the Fama-French factors and stock data. Make sure to handle the data and date alignments correctly when implementing these functions.