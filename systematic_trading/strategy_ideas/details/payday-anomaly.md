<div align="center">
  <h1>Payday Anomaly</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3257064)

## Trading rules

- Investment universe: S&P 500 index
- Buy: 16th day of each month
- Hold: Until the next 16th day
- Repeat: Every month

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1980-2010
- **Annual Return:** 2.57%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.6
- **Annual Standard Deviation:** 4.31%

## Python code

### Backtrader

```python
import backtrader as bt
from datetime import datetime

class PaydayAnomaly(bt.Strategy):
    def __init__(self):
        self.order = None

    def next(self):
        day_of_month = self.data.datetime.date().day

        if self.order:
            return

        if day_of_month == 16:
            if not self.position:
                self.order = self.buy()
        elif day_of_month == 15 and self.position:
            self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm: {order.executed.comm}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm: {order.executed.comm}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def log(self, text):
        print(f'{self.data.datetime.date()}: {text}')

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PaydayAnomaly)
    data = bt.feeds.YahooFinanceData(dataname='^GSPC', fromdate=datetime(2000, 1, 1), todate=datetime(2021, 9, 1))
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    cerebro.run()
```