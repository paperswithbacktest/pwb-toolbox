<div align="center">
  <h1>Price Overreactions in the Forex and Trading Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142)

## Trading rules

- Focus on AUD/USD currency pair
- Identify overreaction day: return > (average return + 2 * standard deviation)
- Base calculations on 50-day period (following Wong, 1997)
- Open position at 17:00 in the direction of overreaction
- Close position by the end of the day

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2008-2018
- **Annual Return:** 4.78%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.76
- **Annual Standard Deviation:** 6.3%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class OverreactionStrategy(bt.Strategy):
    def __init__(self):
        self.data_ohlc = self.datas[0]
        self.returns = bt.ind.Returns(self.data_ohlc.close)
        self.order = None

    def next(self):
        if self.order:
            return

        avg_return = np.mean(self.returns.get(size=50))
        std_dev = np.std(self.returns.get(size=50))
        overreaction_threshold = avg_return + (2 * std_dev)

        if self.data_ohlc.datetime.time() == bt.utils.date.num2date(self.data_ohlc.datetime[0]).replace(hour=17, minute=0).time():
            if self.returns[0] > overreaction_threshold:
                self.order = self.buy()
            elif self.returns[0] < -overreaction_threshold:
                self.order = self.sell()
        elif self.position:
            self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    data = bt.feeds.GenericCSVData(
        dataname='AUDUSD.csv',
        dtformat=('%Y-%m-%d'),
        openinterest=-1
    )

    cerebro.adddata(data)
    cerebro.addstrategy(OverreactionStrategy)
    cerebro.broker.setcash(10000)
    cerebro.run()
```

Make sure to replace `'AUDUSD.csv'` with the correct path to your AUD/USD historical data file, and ensure that the date format in `dtformat` parameter matches your data file’s date format.