<div align="center">
  <h1>What Drives Informed Trading Before Public Releases? Evidence from Natural Gas Inventory Announcements</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2826684)

## Trading rules

- Obtain informed forecast and consensus forecast
- Calculate predictor using forecasts
- Buy natural gas futures when predictor is negative, 90 minutes before announcement
- Sell natural gas futures when predictor is positive, 90 minutes before announcement
- Close position 5 minutes before announcement

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2008-2016
- **Annual Return:** 8.4%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.84
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt

class InformedForecastStrategy(bt.Strategy):
    params = (
        ('informed_forecast', None),
        ('consensus_forecast', None),
        ('buy_time', None),
        ('sell_time', None),
        ('close_time', None),
    )

    def __init__(self):
        self.predictor = self.calculate_predictor(
            self.params.informed_forecast, self.params.consensus_forecast
        )

    def calculate_predictor(self, informed_forecast, consensus_forecast):
        return informed_forecast - consensus_forecast

    def next(self):
        current_time = self.data.datetime.time()
        if current_time == self.params.buy_time and self.predictor < 0:
            self.buy()
        if current_time == self.params.sell_time and self.predictor > 0:
            self.sell()
        if current_time == self.params.close_time:
            self.close()
```

This is a simple Backtrader strategy example that follows the trading rules mentioned. Replace the placeholder lines with your data feed, broker settings, and strategy parameters.