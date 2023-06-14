<div align="center">
  <h1>Multi-Asset Seasonality and Trend-Following Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2710334)

## Trading rules

- Investment universe: commodities with daily front futures price data on Bloomberg
- Long positions: commodities with
    - Positive past 12-month returns
    - Not in bottom seasonality decile (lowest same-calendar-month average past returns, 10-year lookback, min. 5 years of data, exclude past year’s same-month return)
- Short positions: commodities with
    - Negative past 12-month returns
    - Not in top seasonality quintile (highest same-calendar-month average past returns, 10-year lookback, same conditions as above)
- Portfolio rebalancing: monthly
- Asset weighting: equal

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1992-2015
- **Annual Return:** 7.52%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.38
- **Annual Standard Deviation:** 9.32%

## Python code

### Backtrader

To create a trading strategy using Backtrader, follow these steps:

1. Import the necessary libraries
2. Define the custom strategy class
3. Set up the Backtrader engine
4. Load and preprocess the data
5. Run the strategy and analyze the results

Here’s the Python code for your trading rules using Backtrader:

```python
import datetime
import backtrader as bt

# Custom strategy class

class SeasonalityStrategy(bt.Strategy):

def __init__(self):
    self.returns = {}
    self.seasonality = {}
    self.calendar_month = None

def next(self):
    # Rebalance portfolio monthly
    if self.data.datetime.date().month != self.calendar_month:
        self.calendar_month = self.data.datetime.date().month

        # Calculate 12-month returns
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            self.returns[d] = (data.close[0] - data.close[-252]) / data.close[-252]

        # Calculate seasonality
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            past_returns = []

            for i in range(-252, -2520, -252):
                if data.datetime.date(i).month == self.calendar_month:
                    past_returns.append((data.close[i] - data.close[i - 252]) / data.close[i - 252])

            self.seasonality[d] = sum(past_returns) / len(past_returns) if len(past_returns) > 4 else None

        longs = [d for d in self.getdatanames() if self.returns[d] > 0 and self.seasonality[d] is not None and self.seasonality[d] >= sorted(self.seasonality.values())[int(len(self.seasonality) / 10)]]
        shorts = [d for d in self.getdatanames() if self.returns[d] < 0 and self.seasonality[d] is not None and self.seasonality[d] <= sorted(self.seasonality.values())[int(len(self.seasonality) * 4 / 5)]]

        # Rebalance positions
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            if d in longs:
                self.order_target_percent(data, target=1 / len(longs))
            elif d in shorts:
                self.order_target_percent(data, target=-1 / len(shorts))
            else:
                self.order_target_percent(data, target=0)

# Set up Backtrader engine
cerebro = bt.Cerebro()

# Add strategy
cerebro.addstrategy(SeasonalityStrategy)

# Load and preprocess data
commodity_symbols = [‘symbol1’, ‘symbol2’, ‘symbol3’] # Replace with the list of commodity symbols

for symbol in commodity_symbols: data = bt.feeds.PandasData(dataname=get_commodity_data_from_bloomberg(symbol)) # Replace with function to fetch data from Bloomberg cerebro.adddata(data, name=symbol)

# Set initial capital and add analyzers

cerebro.broker.setcash(100000.0)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

# Run the strategy
results = cerebro.run()

# Analyze results
sharpe_ratio = results[0].analyzers.sharpe.get_analysis()
```