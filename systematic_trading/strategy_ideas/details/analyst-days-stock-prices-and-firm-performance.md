<div align="center">
  <h1>Analyst Days, Stock Prices, and Firm Performance</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3272367)

## Trading rules

- Investment Universe: NYSE, AMEX, and NASDAQ stocks (1804 unique stocks with 3890 analyst days)
- Information Source: Publicly released 8-K forms in the SEC’s EDGAR system and/or press releases on analyst days
- Strategy Execution:
    1. Identify stocks with an upcoming analyst day
    2. Buy the stock on the analyst day
    3. Hold the stock for 20 days (approximately one month)
- Portfolio Weighting: Value-weighted

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 2004-2015
- **Annual Return:** 18.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.59
- **Annual Standard Deviation:** 24.08%

## Python code

### Backtrader

```python
import backtrader as bt

class AnalystDaysStrategy(bt.Strategy):
    def __init__(self):
        self.analyst_day_stocks = set()

    def next(self):
        for data in self.datas:
            stock_name = data._name
            # Check if the stock has an upcoming analyst day
            if self.is_analyst_day(stock_name):
                self.analyst_day_stocks.add(stock_name)
                # Buy the stock on the analyst day
                if stock_name not in self.positions:
                    size = self.calculate_value_weighted_size(stock_name)
                    self.buy(data=data, size=size)

        # Hold the stock for 20 days and sell
        for stock_name in list(self.analyst_day_stocks):
            data = self.getdatabyname(stock_name)
            days_held = self.datetime.date() - self.getpositionbyname(stock_name).datetime.date()
            if days_held.days >= 20:
                self.sell(data=data)
                self.analyst_day_stocks.remove(stock_name)

    def is_analyst_day(self, stock_name):
        # Implement logic to check if the stock has an upcoming analyst day based on 8-K forms or press releases
        pass

    def calculate_value_weighted_size(self, stock_name):
        # Implement logic to calculate the value-weighted size for the stock
        pass

# Create a cerebro instance, add data feeds and the strategy, and execute the backtest
cerebro = bt.Cerebro()

# Add data feeds for NYSE, AMEX, and NASDAQ stocks
cerebro.addstrategy(AnalystDaysStrategy)

result = cerebro.run()
```

Please note that you will need to implement the `is_analyst_day` and `calculate_value_weighted_size` methods based on your data sources and the specific rules for identifying analyst days and calculating value-weighted sizes.