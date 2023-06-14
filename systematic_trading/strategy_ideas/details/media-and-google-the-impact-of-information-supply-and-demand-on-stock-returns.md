<div align="center">
  <h1>Media and Google: The Impact of Information Supply and Demand on Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2180409)

## Trading rules

- Investment universe: NYSE, Amex, Nasdaq stocks priced over $5 (excluding closed-end funds, REITs, unit trusts, ADRs, foreign stocks)
- News source: Factiva
- Search volume data: Google Trends (using tickers)
- Information supply scenarios: no news coverage, increased news coverage, decreased news coverage
    - No news coverage: no coverage in past 12 months
    - Increased news coverage: current articles exceed 12-month moving average
    - Decreased news coverage: current articles below 12-month moving average
- Information demand scenarios: no search volume, increased search volume, decreased search volume
    - No search volume: no data from Google Trends due to low/zero volume in past 12 months
    - Increased search volume: above 12-month moving average
    - Decreased search volume: below 12-month moving average
- Monthly portfolio strategy:
    - Long: stocks with increased information supply and demand
    - Short: all other stocks
- Stock weighting: equal weight

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2005-2011
- **Annual Return:** 20.41%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.8
- **Annual Standard Deviation:** 5.87%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
import datetime
from google_trends_scraper import GoogleTrendsScraper
from factiva_scraper import FactivaScraper

class NewsSentiment(bt.Strategy):
    params = dict(
        news_window=12,
        search_window=12,
    )

    def __init__(self):
        self.stocks = self.datas
        self.factiva = FactivaScraper()
        self.gtrends = GoogleTrendsScraper()

    def next(self):
        target_portfolio = []

        for stock in self.stocks:
            ticker = stock._name
            current_date = self.data.datetime.date(0)

            # Get news data
            news_data = self.factiva.get_news_data(ticker, current_date, self.params.news_window)
            news_ma = news_data['count'].rolling(window=self.params.news_window).mean()

            # Get search volume data
            search_data = self.gtrends.get_search_data(ticker, current_date, self.params.search_window)
            search_ma = search_data['count'].rolling(window=self.params.search_window).mean()

            # Determine information supply scenario
            if news_data.iloc[-1]['count'] > news_ma.iloc[-1]:
                news_scenario = 'increase'
            elif news_data.iloc[-1]['count'] < news_ma.iloc[-1]:
                news_scenario = 'decrease'
            else:
                news_scenario = 'no_coverage'

            # Determine information demand scenario
            if search_data.iloc[-1]['count'] > search_ma.iloc[-1]:
                search_scenario = 'increase'
            elif search_data.iloc[-1]['count'] < search_ma.iloc[-1]:
                search_scenario = 'decrease'
            else:
                search_scenario = 'no_volume'

            # Determine target portfolio
            if news_scenario == 'increase' and search_scenario == 'increase':
                target_portfolio.append(stock)

        # Adjust positions
        weight = 1 / len(target_portfolio)
        for stock in self.stocks:
            if stock in target_portfolio:
                self.order_target_percent(stock, target=weight)
            else:
                self.order_target_percent(stock, target=-weight)

# Initialize Cerebro
cerebro = bt.Cerebro()

# Set initial cash and commission
cerebro.broker.set_cash(100000)
cerebro.broker.setcommission(commission=0.001)

# Add stocks data
stock_symbols = ['AAPL', 'GOOGL', 'MSFT']  # Add more stock symbols as needed
start_date = datetime.datetime(2010, 1, 1)
end_date = datetime.datetime(2020, 12, 31)

for symbol in stock_symbols:
    data = bt.feeds.YahooFinanceData(
        dataname=symbol,
        fromdate=start_date,
        todate=end_date,
        plot=False,
    )
    cerebro.adddata(data, name=symbol)

# Add strategy
cerebro.addstrategy(NewsSentiment)

# Run backtest
results = cerebro.run()

# Print final portfolio value
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Please note that this code is a base implementation and will not work without implementing the `FactivaScraper` and `GoogleTrendsScraper` classes for fetching news and search volume data. You will need to integrate appropriate APIs or web scraping techniques to obtain the required data.