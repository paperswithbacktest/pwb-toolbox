<div align="center">
  <h1>Geographic Lead-Lag Effects</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2780139)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ listed stocks
- Assign location variable to each firm based on headquarter ZIP code
- Group headquarter locations by Economic Areas (EAs) as defined by Bureau of Economic Analysis
- Examples of EAs: San Jose-San Francisco-Oakland (CA), Atlanta-Sandy Springs-Gainesville (GA-AL), Houston-Baytown-Huntsville (TX)
- 20 Economic Areas defined in the United States
- Monthly ranking of firms based on average lagged return of other firms in the same region but different sectors
- Sort companies into quintiles
- Go long on top-performing quintile and short on lowest-performing quintile
- Equally weighted portfolio
- Rebalance monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1971-2013
- **Annual Return:** 5.06%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.56
- **Annual Standard Deviation:** 8.99%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class HeadquartersLocationMomentum(bt.Strategy):
    params = (
        ('quintiles', 5),
        ('rebalance_days', 30),
    )

    def __init__(self):
        self.location_data = pd.read_csv('headquarters_zip_economic_areas.csv')  # CSV with firms and their headquarter zip code and economic area
        self.data_dict = {d._name: d for d in self.datas}
        self.rebalance_day = self.params.rebalance_days

    def next(self):
        if self.rebalance_day > 0:
            self.rebalance_day -= 1
        else:
            self.rebalance_day = self.params.rebalance_days
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        location_returns = self.calculate_location_returns()
        quintile_size = len(location_returns) // self.params.quintiles
        sorted_returns = location_returns.sort_values(ascending=False)
        longs = sorted_returns.head(quintile_size).index.tolist()
        shorts = sorted_returns.tail(quintile_size).index.tolist()

        # Close existing positions
        for d in self.data_dict.values():
            if self.getposition(d).size != 0:
                self.close(d)

        # Open new positions
        for location in longs:
            stocks = self.location_data[self.location_data['economic_area'] == location]['ticker'].tolist()
            for stock in stocks:
                self.buy(data=self.data_dict[stock], size=1/len(stocks))

        for location in shorts:
            stocks = self.location_data[self.location_data['economic_area'] == location]['ticker'].tolist()
            for stock in stocks:
                self.sell(data=self.data_dict[stock], size=1/len(stocks))

    def calculate_location_returns(self):
        location_returns = {}
        for location in self.location_data['economic_area'].unique():
            stocks = self.location_data[self.location_data['economic_area'] == location]['ticker'].tolist()
            location_return = sum([self.data_dict[stock].close[-1] / self.data_dict[stock].close[-2] - 1 for stock in stocks]) / len(stocks)
            location_returns[location] = location_return

        return pd.Series(location_returns)


# Initialize Cerebro
cerebro = bt.Cerebro()

# Add stocks data
# Assuming a dictionary called `stock_data` with keys as stock tickers and values as pandas DataFrames with OHLCV data
for ticker, data in stock_data.items():
    cerebro.adddata(bt.feeds.PandasData(dataname=data, name=ticker))

cerebro.addstrategy(HeadquartersLocationMomentum)
cerebro.broker.setcash(100000.0)

# Run Cerebro
result = cerebro.run()
```

Please note that you will need to provide the required input data, such as a CSV file containing information about firms, their headquarter zip code, and economic area, and a dictionary called `stock_data` with keys as stock tickers and values as pandas DataFrames with OHLCV data.