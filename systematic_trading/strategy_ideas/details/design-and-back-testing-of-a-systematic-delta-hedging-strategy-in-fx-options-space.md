<div align="center">
  <h1>Design and Back-Testing of a Systematic Delta-Hedging Strategy in FX Options Space</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2782638)

## Trading rules

- Utilize EURUSD as the underlying asset for high liquidity and minimal bid-offer spread
- Trade one-week at-the-money EURUSD straddles and spot EURUSD for delta-hedging
- Obtain EURUSD tick data from Dukascopy and end-of-day at-the-money volatility data from Bloomberg
- Sell at-the-money EURUSD straddles with one week to expiry on Thursdays at 10:00
- Rebalance portfolio by buying/selling the underlying asset when spot price deviation reaches a mathematically determined threshold
- Refer to page 5 for the formula to determine spot price movement and detailed step-by-step procedure

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2011-2015
- **Annual Return:** 31.48%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 3.15
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class DeltaHedgingStrategy(bt.Strategy):
    def __init__(self):
        self.rebalance_threshold = None  # Replace with threshold calculation from page 5
        self.next_rebalance = None

    def next(self):
        if not self.position:
            if self.data.datetime.date(0).weekday() == 3 and self.data.datetime.time(0).hour == 10:
                self.sell(size=1)  # Sell at-the-money straddle
                self.next_rebalance = self.data.datetime.datetime(0) + datetime.timedelta(weeks=1)

        if self.position and self.next_rebalance:
            if abs(self.data.close[0] - self.position.price) >= self.rebalance_threshold:
                if self.data.close[0] > self.position.price:
                    self.buy(size=self.position.size)  # Buy underlying asset for delta hedging
                else:
                    self.sell(size=self.position.size)  # Sell underlying asset for delta hedging

            if self.data.datetime.datetime(0) >= self.next_rebalance:
                self.close()  # Close straddle position
                self.next_rebalance = None

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Replace the following with the correct data feeds for EURUSD tick data and end-of-day volatility data
    data = bt.feeds.GenericCSVData(dataname='your_eurusd_tick_data.csv')
    cerebro.adddata(data)
    cerebro.addstrategy(DeltaHedgingStrategy)
    cerebro.broker.setcash(100000.0)
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Please note that this code is just a starting point and will need to be adjusted according to your specific data sources and the formula for determining the rebalance threshold as mentioned on page 5 of the document you are referring to.