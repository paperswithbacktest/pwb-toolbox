<div align="center">
  <h1>Measuring and Trading Volatility on the US Stock Market: A Regime Switching Approach</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3257073)

## Trading rules

- Investment universe consists of SPY, SH, VXX and XIV
- Calculate the relative difference between front month VIX futures and spot VIX
- If relative basis is above the upper buy threshold (BU), hold XIV and hedge with SH
- If relative basis is below the lower buy threshold (BL), hold VXX and hedge with SPY
- Close position when the relative basis falls below the upper sell threshold (SU) or above the lower sell threshold (SL)
- SU may be set equal to or lower than BU and SL may be set higher than BL to avoid frequent trading
- Best results are achieved with 0% hedge ratio but multiple hedging levels are possible with different results.

## Statistics

- **Markets Traded:** Equities, Financial instruments
- **Period of Rebalancing:** Daily
- **Backtest period:** 2006-2014
- **Annual Return:** 69%
- **Maximum Drawdown:** -24.5%
- **Sharpe Ratio:** 1.67
- **Annual Standard Deviation:** 39%

## Python code

### Backtrader

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (
        ('spy', 0.5),
        ('sh', 0.5),
        ('vxx', 0.5),
        ('xiv', 0.5),
        ('bu', 0.5),
        ('bl', -0.5),
        ('su', 0.1),
        ('sl', -0.1),
    )

    def __init__(self):
        self.vix1 = self.datas[0]
        self.vix2 = self.datas[1]
        self.spy = self.datas[2]
        self.sh = self.datas[3]
        self.vxx = self.datas[4]
        self.xiv = self.datas[5]

    def next(self):
        rel_diff = (self.vix2.close[0] - self.vix1.close[0]) / self.vix1.close[0]

        if rel_diff > self.params.bu:
            self.order_target_percent(self.xiv, target=1.0)
            self.order_target_percent(self.sh, target=-1.0)
        elif rel_diff < self.params.bl:
            self.order_target_percent(self.vxx, target=1.0)
            self.order_target_percent(self.spy, target=-1.0)
        elif rel_diff < self.params.su and rel_diff > self.params.sl:
            self.close()

# Initialize Cerebro
cerebro = bt.Cerebro()

# Add data feeds for vix1, vix2, spy, sh, vxx, xiv
# Replace ... with the appropriate data feeds for each instrument
data_vix1 = bt.feeds.YourDataFeed(...)
data_vix2 = bt.feeds.YourDataFeed(...)
data_spy = bt.feeds.YourDataFeed(...)
data_sh = bt.feeds.YourDataFeed(...)
data_vxx = bt.feeds.YourDataFeed(...)
data_xiv = bt.feeds.YourDataFeed(...)

# Add all data feeds
cerebro.adddata(data_vix1)
cerebro.adddata(data_vix2)
cerebro.adddata(data_spy)
cerebro.adddata(data_sh)
cerebro.adddata(data_vxx)
cerebro.adddata(data_xiv)

# Add strategy
cerebro.addstrategy(MyStrategy,
                    spy=params['spy'],
                    sh=params['sh'],
                    vxx=params['vxx'],
                    xiv=params['xiv'],
                    bu=params['bu'],
                    bl=params['bl'],
                    su=params['su'],
                    sl=params['sl'])

# Run backtest
results = cerebro.run()
```