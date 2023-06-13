<div align="center">
  <h1>DRIPs and the Dividend Pay Date Effect</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2172448)

## Trading rules

- The investment universe is limited to NYSE, AMEX and NASDAQ stocks with company-sponsored DRIPs.
- Daily, at close of market, investors purchase stocks that have dividend payday on the next working day.
- The stocks are held for only 1 day.
- Stocks are weighted equally within the portfolio.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1996-2009
- **Annual Return:** 70.2%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.41
- **Annual Standard Deviation:** 27.5%

## Python code

### Backtrader

```python
# Import necessary packages
import backtrader as bt
import pandas as pd
import os

class DRIPStocks(bt.Strategy):

    def log(self, txt, dt=None):
        """ Logging function for the strategy"""
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Filter for stocks with company-sponsored DRIPs listed on NYSE, AMEX and NASDAQ
        self.stocks = [
            stock for stock in os.listdir('stock_data/')
            if stock.endswith('.csv')
            and 'NYSE' in stock or 'AMEX' in stock or 'NASDAQ' in stock
            and pd.read_csv(f'stock_data/{stock}')['DRIP'].values[0] == 'Yes'
        ]

        # Create data feeds for each stock
        self.datafeeds = [
            bt.feeds.YahooFinanceCSVData(
                dataname=f'stock_data/{stock}',
                fromdate=self.datas[0].datetime.date(0),
                todate=self.datas[0].datetime.date(0) + pd.DateOffset(1),
                reverse=False,
                adjclose=True
            )
            for stock in self.stocks
        ]

        # Create a list of stocks to buy based on payday
        self.stocks_to_buy = []
        for df, data in zip(self.datas, self.datafeeds):
            if df.datetime.date(0) in pd.DatetimeIndex(data.pays).date:
                self.stocks_to_buy.append(df)

    def next(self):
        # Buy stocks on payday and hold for 1 day
        if self.stocks_to_buy:
            for stock in self.stocks_to_buy:
                self.order_target_percent(stock, 1/len(self.stocks_to_buy))

        # Remove stocks from the list after buying
        self.stocks_to_buy.clear()
```

Note: This code assumes that the data for the stocks is stored in a directory called “stock_data” and that each stock’s data is stored in a separate csv file with the stock’s symbol as the filename (e.g. AAPL.csv). The csv file should contain columns for ‘Date’, ‘Open’, ‘High’, ‘Low’, ‘Close’, ‘Adj Close’, ‘Volume’, and ‘DRIP’ (which should indicate ‘Yes’ if the stock has a company-sponsored DRIP or ‘No’ if not).