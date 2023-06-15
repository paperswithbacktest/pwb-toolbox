<div align="center">
  <h1>The Turn-of-The-Month-Effect: Evidence from Periodic Generalized Autoregressive Conditional Heteroskedasticity (PGARCH) Model</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2479295)

## Trading rules

- Buy SPY ETF 1 day (some papers say 4 days) before the end of the month
- Sell the SPY ETF on the 3rd trading day of the new month
- Sell the ETF at the close of the 3rd trading day of the new month

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1926-2005
- **Annual Return:** 7.2%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.04
- **Annual Standard Deviation:** 6.9%

## Python code

### Backtrader

```python
# Define the strategy
class MonthEndStrategy(bt.Strategy):

    def __init__(self):
        # Initialize the window
        self.add_window = True

    def next(self):
        # Check if it's the last day of the month
        if self.data.datetime.date().day == calendar.monthrange(self.data.datetime.date().year, self.data.datetime.date().month)[1]:
            # Buy SPY 1 day before the last day of the month
            self.buy(data=self.datas[0], size=1)
            self.add_window = False

        # Check if it's the third day of the new month
        elif self.data.datetime.date().day == 3 and not self.add_window:
            # Sell SPY at the close of the 3rd trading day of the new month
            self.sell(data=self.datas[0], size=1)
            self.add_window = True
```

Note that this code is based on a daily time frame. If you want to use a different time frame, you will need to change the code accordingly.