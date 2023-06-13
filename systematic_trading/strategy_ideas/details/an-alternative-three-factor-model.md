<div align="center">
  <h1>An Alternative Three-Factor Model</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1418117)

## Trading rules

- Investment universe: All stocks on NYSE, AMEX, and Nasdaq with sales over $10 million
- Sort stocks into two groups based on market capitalization
- Divide each group into deciles using Return on Assets (ROA)
- ROA = quarterly earnings (Compustat IBQ) / one-quarter-lagged assets (Compustat ATQ)
- Go long on top 3 deciles from each market cap group
- Go short on bottom 3 deciles from each market cap group
- Rebalance strategy monthly with equal-weighted stocks

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1972-2006
- **Annual Return:** 12.15%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 13.36%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class ROAStrategy(bt.Strategy):
    def __init__(self):
        self.stocks_with_sales = self.datas

    def next(self):
        # Filter stocks with sales over $10 million
        filtered_stocks = [d for d in self.stocks_with_sales if d.sales[0] > 10000000]

        # Sort stocks into two groups based on market capitalization
        half = len(filtered_stocks) // 2
        sorted_stocks = sorted(filtered_stocks, key=lambda d: d.market_cap[0], reverse=True)
        large_cap, small_cap = sorted_stocks[:half], sorted_stocks[half:]

        # Calculate ROA for all stocks
        for stock in filtered_stocks:
            stock.roa = stock.quarterly_earnings[0] / stock.lagged_assets[0]

        # Sort stocks in each group by ROA and divide into deciles
        large_cap_sorted = sorted(large_cap, key=lambda d: d.roa, reverse=True)
        small_cap_sorted = sorted(small_cap, key=lambda d: d.roa, reverse=True)
        decile_large = len(large_cap_sorted) // 10
        decile_small = len(small_cap_sorted) // 10

        # Go long on top 3 deciles from each market cap group
        long_stocks = large_cap_sorted[:3 * decile_large] + small_cap_sorted[:3 * decile_small]

        # Go short on bottom 3 deciles from each market cap group
        short_stocks = large_cap_sorted[-3 * decile_large:] + small_cap_sorted[-3 * decile_small]

        # Rebalance strategy monthly with equal-weighted stocks
        for stock in long_stocks:
            self.order_target_percent(stock, target=1.0 / len(long_stocks))
        for stock in short_stocks:
            self.order_target_percent(stock, target=-1.0 / len(short_stocks))
        for stock in self.stocks_with_sales:
            if stock not in long_stocks and stock not in short_stocks:
                self.order_target_percent(stock, target=0)
```

Note: This code assumes that you have already prepared your data feeds with the required data fields such as `sales`, `market_cap`, `quarterly_earnings`, and `lagged_assets`. You will also need to configure the backtrader cerebro object to include your data feeds and use the `ROAStrategy` class.