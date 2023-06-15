<div align="center">
  <h1>Short-Term Residual Reversal</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1911449)

## Trading rules

- Investment universe: Common U.S. stocks (NYSE, AMEX, NASDAQ) with market cap above NYSE median and price above $1
- Linear regression: Market factor, Small-cap factor, Value factor, Momentum factor as independent variables
- Input data: Stock returns over preceding 36 months (dependent variable)
- Calculate residual returns for each stock
- Standardize estimated residual returns by dividing by their 36-month standard deviation
- Construct residual reversal portfolios by sorting stocks into deciles based on standardized residual returns each month
- Winner portfolio: Top 10% of stocks with highest returns
- Loser portfolio: Bottom 10% of stocks with lowest returns
- Strategy: Long loser portfolio, short winner portfolio
- Portfolio weighting: Equal weighting for all stocks
- Rebalancing: Monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1929-2008
- **Annual Return:** 17.32%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.06
- **Annual Standard Deviation:** 12.57%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class ResidualReversal(bt.Strategy):
    params = dict(
        lookback=36,
        num_deciles=10,
        min_market_cap=0,
        min_price=1
    )

    def __init__(self):
        self.stock_returns = {}
        self.residual_returns = {}
        self.rankings = {}

    def prenext(self):
        self.next()

    def next(self):
        # Get market capitalization and prices for all stocks
        market_caps = {data: data.market_cap[0] for data in self.datas}
        prices = {data: data.close[0] for data in self.datas}

        # Filter stocks based on market capitalization and price
        filtered_stocks = [data for data in self.datas if market_caps[data] > self.params.min_market_cap and prices[data] > self.params.min_price]

        # Calculate stock returns for the past 36 months
        for stock in filtered_stocks:
            self.stock_returns[stock] = (stock.close[0] - stock.close[-self.params.lookback]) / stock.close[-self.params.lookback]

        # Prepare data for linear regression
        X = np.column_stack([stock.market_factor.get(size=self.params.lookback) for stock in filtered_stocks])
        X = np.column_stack([X, [stock.small_cap_factor.get(size=self.params.lookback) for stock in filtered_stocks]])
        X = np.column_stack([X, [stock.value_factor.get(size=self.params.lookback) for stock in filtered_stocks]])
        X = np.column_stack([X, [stock.momentum_factor.get(size=self.params.lookback) for stock in filtered_stocks]])
        y = np.array(list(self.stock_returns.values()))

        # Perform linear regression and calculate residual returns
        model = LinearRegression()
        model.fit(X, y)
        residuals = y - model.predict(X)

        for i, stock in enumerate(filtered_stocks):
            self.residual_returns[stock] = residuals[i]

        # Standardize residual returns
        std_residuals = np.std(list(self.residual_returns.values()))
        standardized_residuals = {stock: residual / std_residuals for stock, residual in self.residual_returns.items()}

        # Rank stocks based on standardized residual returns
        sorted_stocks = sorted(standardized_residuals.items(), key=lambda x: x[1])
        decile_size = len(sorted_stocks) // self.params.num_deciles

        # Construct winner and loser portfolios
        loser_portfolio = [stock for stock, _ in sorted_stocks[:decile_size]]
        winner_portfolio = [stock for stock, _ in sorted_stocks[-decile_size:]]

        # Implement long/short strategy
        for stock in self.datas:
            if stock in loser_portfolio:
                self.order_target_percent(stock, target=1 / len(loser_portfolio))
            elif stock in winner_portfolio:
                self.order_target_percent(stock, target=-1 / len(winner_portfolio))
            else:
                self.order_target_percent(stock, target=0)

# Add data feeds, broker, and cerebro configurations below
```

Please note that this code assumes that the Market factor, Small-cap factor, Value factor, and Momentum factor are available as lines in the data feeds. Additionally, you’ll need to add data feeds, configure the broker, and set up the cerebro instance before running the strategy.