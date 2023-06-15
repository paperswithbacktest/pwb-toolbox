<div align="center">
  <h1>One-Month Individual Stock Return Reversals and Industry Return Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1914629)

## Trading rules

- Investment universe: NYSE, AMEX, NASDAQ stocks (data from CRSP Compustat database)
- Industry sorting: Utilize Fama and French library data (http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) to sort industries into deciles based on previous month’s performance
- Stock selection: Focus on top-performing industry decile stocks
- Further sorting: Organize selected stocks into deciles based on previous month’s performance
- Position: Go long on lowest return stocks from the previous month
- Portfolio: Equally weighted, monthly rebalanced

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1931-2010
- **Annual Return:** 50.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.11
- **Annual Standard Deviation:** 42.16%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.feeds as btfeeds
import pandas as pd
import requests

class IndustryRotationStrategy(bt.Strategy):
    params = (
        ('industry_decile', 0.9),
        ('stock_decile', 0.1),
    )

    def __init__(self):
        self.monthly_rebalance = False

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            self.monthly_rebalance = True
        else:
            self.monthly_rebalance = False

        if self.monthly_rebalance:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        industries = self.get_industries_performance()
        top_decile_industries = industries.tail(int(len(industries) * self.params.industry_decile))
        stocks = self.get_stocks_performance(top_decile_industries)
        lowest_decile_stocks = stocks.head(int(len(stocks) * self.params.stock_decile))

        for stock in lowest_decile_stocks:
            self.order_target_percent(stock, target=1 / len(lowest_decile_stocks))

    def get_industries_performance(self):
        # Fetch Fama and French library data and return sorted industries dataframe
        # Replace this placeholder function with the actual implementation to fetch industry performance data
        industries_data = requests.get("URL_TO_FETCH_INDUSTRY_PERFORMANCE_DATA").json()
        industries_df = pd.DataFrame(industries_data)
        industries_df.sort_values('performance', ascending=False, inplace=True)
        return industries_df

    def get_stocks_performance(self, top_decile_industries):
        # Fetch stock data and return sorted stocks dataframe within top-performing industries
        # Replace this placeholder function with the actual implementation to fetch stock performance data
        stocks_data = requests.get("URL_TO_FETCH_STOCK_PERFORMANCE_DATA").json()
        stocks_df = pd.DataFrame(stocks_data)
        top_stocks_df = stocks_df[stocks_df['industry'].isin(top_decile_industries['industry'])]
        top_stocks_df.sort_values('performance', ascending=False, inplace=True)
        return top_stocks_df

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Load historical data for stocks and industry performance
    # Add appropriate data feeds to cerebro

    cerebro.addstrategy(IndustryRotationStrategy)
    cerebro.run()
```

Please note that this code is a skeleton for the trading strategy and you will need to provide the appropriate data feeds and implement the functions `get_industries_performance()` and `get_stocks_performance()` according to your data sources.