<div align="center">
  <h1>Market Timing with Aggregate and Idiosyncratic Stock Volatilities</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=869447)

## Trading rules

- Calculate market variance for the previous quarter using squared daily excess stock market returns
- Determine idiosyncratic variance for each S&P 500 stock using regression analysis with Fama and French factors (Market, Size, Book-to-Market) as independent variables
- Weight and sum residuals from regression based on each stock’s market cap to obtain summary idiosyncratic variance
- Estimate expected excess stock market return for the upcoming quarter using regression with market variance and summary idiosyncratic variance as independent variables
- Set equity weight in the portfolio based on expected excess stock market return, expected stock market variance, and investor’s risk aversion coefficient
- Rebalance portfolio quarterly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1968-2004
- **Annual Return:** 20.07%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.43
- **Annual Standard Deviation:** 37.8%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class MarketTimingStrategy(bt.Strategy):
    def __init__(self):
        self.quarterly_timer = 0

    def next(self):
        self.quarterly_timer += 1
        if self.quarterly_timer % 63 == 0:  # Rebalance every quarter (approx. 63 trading days)
            market_returns = self.data.close.pct_change()
            excess_market_returns = market_returns - self.data.close.get(size=252).mean()

            # Calculate market variance for the previous quarter
            market_variance = np.square(excess_market_returns[-63:]).sum() / 63

            # Determine idiosyncratic variance for each stock in the S&P 500
            idiosyncratic_variances = []
            market_caps = []

            for stock_data in self.datas:
                stock_returns = stock_data.close.pct_change()
                excess_stock_returns = stock_returns - stock_data.close.get(size=252).mean()

                # Fama-French factors
                market_factor = excess_stock_returns - excess_market_returns
                size_factor = stock_data.size
                book_to_market_factor = stock_data.book_to_market

                X = np.column_stack((market_factor, size_factor, book_to_market_factor))
                y = excess_stock_returns

                # Regression analysis
                model = LinearRegression()
                model.fit(X, y)
                residuals = y - model.predict(X)
                idiosyncratic_variance = np.square(residuals).sum() / len(residuals)
                idiosyncratic_variances.append(idiosyncratic_variance)
                market_caps.append(stock_data.market_cap)

            # Weight and sum residuals
            weights = np.array(market_caps) / sum(market_caps)
            summary_idiosyncratic_variance = np.dot(weights, idiosyncratic_variances)

            # Estimate expected excess stock market return for the upcoming quarter
            X = np.column_stack((market_variance, summary_idiosyncratic_variance))
            y = excess_market_returns

            model = LinearRegression()
            model.fit(X, y)
            expected_excess_return = model.predict(X)

            # Set equity weight in the portfolio
            risk_aversion_coefficient = 1  # Modify as needed
            equity_weight = expected_excess_return / (risk_aversion_coefficient * market_variance)

            # Rebalance portfolio
            for i, stock_data in enumerate(self.datas):
                self.order_target_percent(stock_data, target=equity_weight[i])

# Initialize Cerebro
cerebro = bt.Cerebro()

# Add data feeds for S&P 500 stocks here
# Replace ... with the appropriate data feeds for each stock
data1 = bt.feeds.YourDataFeed(...)
data2 = bt.feeds.YourDataFeed(...)
# Add all S&P 500 data feeds
cerebro.adddata(data1)
cerebro.adddata(data2)
# ...

# Add strategy
cerebro.addstrategy(MarketTimingStrategy)

# Run backtest
results = cerebro.run()
```