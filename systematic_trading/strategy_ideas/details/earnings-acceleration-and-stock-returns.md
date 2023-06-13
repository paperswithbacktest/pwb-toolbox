<div align="center">
  <h1>Earnings Acceleration and Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3057632)

## Trading rules

- Investment universe: NYSE, AMEX, NASDAQ firms (excluding financial and utility firms with SIC codes 6000-6999 and 4900-4949)
- Calculate earnings acceleration:
    1. Fraction 1: (EPS of stock i at quarter t - EPS of stock i at quarter t-4) / stock price at end of quarter t-1
    2. Fraction 2: (EPS of stock i at quarter t-1 - EPS of stock i at quarter t-5) / stock price at end of quarter t-2
    3. Earnings acceleration: Fraction 1 - Fraction 2
- Long highest earnings acceleration decile, short lowest earnings acceleration decile
- Holding period: 1 month (starting 2 days after quarter t’s earnings announcement, ending on day 30)
- Portfolio: Value-weighted, daily rebalancing due to announcement dates

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1972-2015
- **Annual Return:** 23.87%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.44
- **Annual Standard Deviation:** 13.81%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class EarningsAcceleration(bt.Strategy):
    params = (
        ('rebalance_days', 30),
    )

    def __init__(self):
        self.earnings_acceleration = dict()

    def next(self):
        if len(self.data) % self.params.rebalance_days == 0:
            self.rank_stocks()
            self.rebalance_portfolio()

    def rank_stocks(self):
        for d in self.datas:
            eps = d.eps.get(size=6)
            prices = d.close.get(size=3)
            fraction1 = (eps[-1] - eps[-5]) / prices[-2]
            fraction2 = (eps[-2] - eps[-6]) / prices[-3]
            earnings_accel = fraction1 - fraction2
            self.earnings_acceleration[d] = earnings_accel
        self.earnings_acceleration = {k: v for k, v in sorted(self.earnings_acceleration.items(), key=lambda item: item[1], reverse=True)}

    def rebalance_portfolio(self):
        num_stocks = len(self.datas)
        num_decile = num_stocks // 10
        for i, d in enumerate(self.earnings_acceleration.keys()):
            if i < num_decile:
                self.order_target_percent(d, target=1 / num_decile)
            elif i >= num_stocks - num_decile:
                self.order_target_percent(d, target=-1 / num_decile)
            else:
                self.order_target_percent(d, 0)

# Backtrader engine and settings
cerebro = bt.Cerebro()

# Add stocks data to the engine
stocks_data = pd.read_csv('your_stock_data.csv')
for stock_data in stocks_data:
    data = bt.feeds.PandasData(dataname=stock_data)
    cerebro.adddata(data)

# Add strategy to the engine
cerebro.addstrategy(EarningsAcceleration)

# Run the backtest
results = cerebro.run()

# Plot the results
cerebro.plot()
```

Please note that you’ll need to replace ‘your_stock_data.csv’ with your actual stock data file containing historical price and earnings per share (EPS) data for the investment universe (NYSE, AMEX, NASDAQ firms). Make sure the data is already filtered to exclude financial and utility firms with SIC codes 6000-6999 and 4900-4949.