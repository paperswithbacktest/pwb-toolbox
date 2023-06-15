<div align="center">
  <h1>Relief Rallies after FOMC Announcements as a Resolution of Uncertainty</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2810262)

## Trading rules

- Buy E-mini S&P 500 index futures contract.
- Buy the contract five minutes before the FOMC statement, including the release of SEP.
- Hold the position for 55 minutes after the announcement.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2012-2015
- **Annual Return:** 10.5%
- **Maximum Drawdown:** Simple strategy
- **Sharpe Ratio:** 2.1
- **Annual Standard Deviation:** target annual volatility of 5%

## Python code

### Backtrader

```python
# Import backtrader and define the strategy class
import backtrader as bt

class MyStrategy(bt.Strategy):

    def __init__(self):
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None

    def next(self):
        # If no order is open and it is 5 minutes before the FOMC statement
        if self.order is None and self.datas[0].datetime.date() == '2019-09-18' and self.datas[0].datetime.time() >= datetime.time(12, 55):
            self.order = self.buy(size=1)

        # If the position has been open for 55 minutes
        if self.order is not None and len(self) - self.order.created[0] >= 55:
            self.close()
```

Note: This is an example and the dates and times provided are specific to one particular FOMC statement. In real-life trading, a more robust and dynamic solution would be required to account for fluctuations in release times and dates.