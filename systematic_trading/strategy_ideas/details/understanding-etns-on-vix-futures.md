<div align="center">
  <h1>Understanding ETNs on VIX Futures</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2043061)

## Trading rules

- The investment universe consists of two ETNs – XVIX and XVZ
- Two VIX futures market states are considered – contango and backwardation
- The ratio of the 30-day implied volatility index (VIX) to the 93-day implied volatility index (VXV) is calculated each day
- When the ratio is lower than 1, short end of the VIX term structure is in contango; when it is higher than 1, short end of the VIX term structure is in backwardation
- The trading strategy holds XVIX when the VIX term structure is in contango
- The trading strategy holds XVZ when VIX term structure is in backwardation
- Portfolio is rebalanced daily

## Statistics

- **Markets Traded:** Options
- **Period of Rebalancing:** Daily
- **Backtest period:** 2004-2011
- **Annual Return:** 30.8%
- **Maximum Drawdown:** Moderately complex strategy
- **Sharpe Ratio:** 1.14
- **Annual Standard Deviation:** 23.49%

## Python code

### Backtrader

```python
import backtrader as bt

class VIXTermStructure(bt.Strategy):
    def __init__(self):
        self.xvix = self.datas[0]  # 30-day VIX data feed
        self.xvz = self.datas[1]  # 93-day VXV data feed

    def next(self):
        vix_30d = self.xvix.lines.close[0]
        vxv_93d = self.xvz.lines.close[0]
        ratio = vix_30d / vxv_93d

        if ratio < 1:
            self.order_target_percent(self.xvix, target=1.0)
            self.order_target_percent(self.xvz, target=0.0)
        elif ratio > 1:
            self.order_target_percent(self.xvix, target=0.0)
            self.order_target_percent(self.xvz, target=1.0)

        self.rebalance()

    def rebalance(self):
        for data in self.datas:
            self.order_target_percent(data, target=1.0 / len(self.datas))

cerebro = bt.Cerebro()

# Add VIX and VXV data feeds
vix_data = bt.feeds.YahooFinanceData(dataname='VIX', fromdate=start_date, todate=end_date)
vxv_data = bt.feeds.YahooFinanceData(dataname='VXV', fromdate=start_date, todate=end_date)
cerebro.adddata(vix_data)
cerebro.adddata(vxv_data)

cerebro.addstrategy(VIXTermStructure)
cerebro.broker.setcash(100000.0)

print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
cerebro.run()
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Note: Assumes that the data for XVIX is passed as the first parameter and the data for XVZ is passed as the second parameter when creating the strategy object. Also, assumes that the order_target_percent function is used to allocate funds to each security. Finally, the output assumes that the necessary data feeds are added and backtesting is done separately.