<div align="center">
  <h1>The Poverty of Academic Finance Research: Spread Trading Strategies in the Crude Oil Futures Market</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2617585)

## Trading rules

- Calculate the 20-day moving average of WTI/Brent spread each day
- If the current spread value is above the SMA 20, enter a short position on the spread on close
- bet that the spread will decrease to the fair value represented by SMA 20
- Close the trade at the close of the trading day when the spread crosses below fair value
- If the current spread value is below SMA 20, enter a long position betting that the spread will increase
- Close the trade at the close of the trading day when the spread crosses above fair value.

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1995-2004
- **Annual Return:** 39.4%
- **Maximum Drawdown:** -13.45%
- **Sharpe Ratio:** 1.64
- **Annual Standard Deviation:** 21.65%

## Python code

### Backtrader

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(self.data, period=20)

    def next(self):
        if self.data[0] > self.sma[0]:
            self.sell()
        elif self.data[0] < self.sma[0]:
            self.buy()
```