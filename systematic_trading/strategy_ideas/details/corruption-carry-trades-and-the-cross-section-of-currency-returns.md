<div align="center">
  <h1>Corruption, Carry Trades, and the Cross Section of Currency Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2961743)

## Trading rules

- Investment universe: 17 most liquid currency pairs against US dollar
- Divide currencies into terciles based on previous year’s Corruption Perception Index (CPI) scores
    - Low CPI score: high corruption perception
    - High CPI score: low corruption perception
- Create two portfolios:
    1. First portfolio: currencies of five countries with the lowest CPI scores
    2. Third portfolio: currencies of five countries with the highest CPI scores
- Form a zero-cost portfolio:
    - Long on currencies in the third portfolio (high CPI scores)
    - Short on currencies in the first portfolio (low CPI scores)
- Rebalance the portfolio annually

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Yearly
- **Backtest period:** 2001-2016
- **Annual Return:** 6.04%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.74
- **Annual Standard Deviation:** 8.14%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class CorruptionPerceptionIndexStrategy(bt.Strategy):
    params = (
        ('investment_universe', ['AUDUSD', 'EURUSD', 'GBPUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']),
    )

    def __init__(self):
        self.cpi_data = pd.read_csv('cpi_data.csv')
        self.current_year = None

    def next(self):
        if self.current_year != self.data.datetime.date().year:
            self.current_year = self.data.datetime.date().year
            self.rebalance()

    def rebalance(self):
        cpi_previous_year = self.cpi_data[self.cpi_data['year'] == self.current_year - 1]
        terciles = cpi_previous_year['cpi'].quantile([1/3, 2/3])
        first_tercile = cpi_previous_year[cpi_previous_year['cpi'] <= terciles.iloc[0]].nlargest(5, 'cpi')
        third_tercile = cpi_previous_year[cpi_previous_year['cpi'] >= terciles.iloc[1]].nsmallest(5, 'cpi')

        for d in self.getdatanames():
            if d in first_tercile['currency'].values:
                self.sell(data=self.getdatabyname(d))
            elif d in third_tercile['currency'].values:
                self.buy(data=self.getdatabyname(d))

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(CorruptionPerceptionIndexStrategy)

    for currency_pair in CorruptionPerceptionIndexStrategy.params.investment_universe:
        data = bt.feeds.GenericCSVData(
            dataname=f'{currency_pair}.csv',
            dtformat=('%Y-%m-%d'),
            openinterest=-1,
            timeframe=bt.TimeFrame.Days
        )
        cerebro.adddata(data, name=currency_pair)

    cerebro.run()
```

Please note that this code assumes you have a CSV file named ‘cpi_data.csv’ containing the annual CPI data with columns ‘year’, ‘currency’, and ‘cpi’, and separate CSV files for each currency pair’s historical price data with columns ‘Date’, ‘Open’, ‘High’, ‘Low’, ‘Close’, and ‘Volume’. You need to prepare these CSV files and make sure their formats match the expected formats in the code.