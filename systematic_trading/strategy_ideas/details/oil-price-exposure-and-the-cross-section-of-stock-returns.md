<div align="center">
  <h1>Oil price exposure and the cross section of stock returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3164353)

## Trading rules

- Investment universe: CRSP/COMPUSTAT database stocks
- Estimate "oil earnings beta" for each stock at the end of each calendar quarter using equation 1 on page 5 (rolling regression with data from the last 12 quarters)
- Calculate oil earnings surprise for stock i in quarter Q as the product of the stock’s oil earnings beta estimate and the most recent quarterly change in oil prices
- Form quintile portfolios:
    - Long the top quintile (highest oil earnings surprises)
    - Short the bottom quintile (lowest oil earnings surprises)
- Hold portfolios during the following quarter
- Strategy is value-weighted

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1974-2015
- **Annual Return:** 6.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.21
- **Annual Standard Deviation:** 13.5%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
import statsmodels.api as sm

class OilEarningsSurprise(bt.Strategy):
    params = (
        ("lookback_quarters", 12),
        ("portfolio_quintiles", 5),
    )

    def __init__(self):
        self.oil_price = bt.feeds.YahooFinanceCSVData(dataname="PATH_TO_OIL_PRICE_DATA")
        self.dnames = self.datas

    def next(self):
        if self.datetime.date().month % 3 == 0:  # Rebalance every quarter
            oil_earnings_betas = []
            for d in self.dnames:
                stock_prices = self.get_stock_prices(d)
                oil_prices = self.get_oil_prices()
                oil_returns = oil_prices.pct_change().dropna()
                stock_returns = stock_prices.pct_change().dropna()
                model = sm.OLS(stock_returns, sm.add_constant(oil_returns)).fit()
                oil_earnings_beta = model.params[1]
                oil_earnings_betas.append(oil_earnings_beta)

            oil_earnings_surprises = [
                beta * (self.oil_price.close[0] - self.oil_price.close[-1])
                for beta in oil_earnings_betas
            ]

            quintile_size = len(self.dnames) // self.p.portfolio_quintiles
            long_stocks = np.argsort(oil_earnings_surprises)[-quintile_size:]
            short_stocks = np.argsort(oil_earnings_surprises)[:quintile_size]

            for i, d in enumerate(self.dnames):
                if i in long_stocks:
                    self.order_target_percent(d, target=1 / quintile_size)
                elif i in short_stocks:
                    self.order_target_percent(d, target=-1 / quintile_size)
                else:
                    self.order_target_percent(d, target=0)

    def get_stock_prices(self, d):
        return pd.Series([d.close[i] for i in range(-self.p.lookback_quarters * 3, 1)], index=pd.date_range(end=self.datetime.date(), periods=self.p.lookback_quarters * 3 + 1, closed='right'))

    def get_oil_prices(self):
        return pd.Series([self.oil_price.close[i] for i in range(-self.p.lookback_quarters * 3, 1)], index=pd.date_range(end=self.datetime.date(), periods=self.p.lookback_quarters * 3 + 1, closed='right'))

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Add stocks from CRSP/COMPUSTAT database
    for stock in STOCKS_FROM_DATABASE:
        data = bt.feeds.YahooFinanceCSVData(dataname=stock["csv_path"])
        cerebro.adddata(data)

    cerebro.addstrategy(OilEarningsSurprise)
    cerebro.broker.setcash(1000000.0)
    cerebro.run()
```

Replace `PATH_TO_OIL_PRICE_DATA` with the path to your oil price data file and `STOCKS_FROM_DATABASE` with a list of dictionaries containing the stock ticker and path to the stock data in CSV format. This code assumes you are using Yahoo Finance CSV data for both oil price and stock data.