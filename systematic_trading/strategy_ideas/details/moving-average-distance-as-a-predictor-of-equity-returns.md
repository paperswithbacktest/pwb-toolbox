<div align="center">
  <h1>Moving Average Distance as a Predictor of Equity Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111334)

## Trading rules

Equity Trading Strategy: Distance Between Short and Long-Term Moving Averages

- Investment universe: U.S. firms on NYSE, AMEX, NASDAQ with share codes 10/11, positive equity book value in Compustat, and other specific criteria
- Exclude stocks: end-of-month price below $5, not traded during the month, insufficient return or firm characteristic data
- Calculate MAD: Divide MA(21) by MA(200) (21-day and 200-day moving averages)
- Set threshold: Fixed value of 0.2
- Long positions: MAD equal to or greater than 1.2
- Short positions: MAD equal to or less than 0.8
- Portfolio weighting: Equally-weighted stocks
- Rebalancing: Monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1977-2015
- **Annual Return:** 10.12%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.43
- **Annual Standard Deviation:** 14.15%

## Python code

### Backtrader

```python
import backtrader as bt

class MADStrategy(bt.Strategy):
    params = (
        ('ma_short', 21),
        ('ma_long', 200),
        ('long_threshold', 1.2),
        ('short_threshold', 0.8),
    )

    def __init__(self):
        self.ma_short = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.ma_short
        )
        self.ma_long = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.ma_long
        )
        self.mad = self.ma_short / self.ma_long

    def next(self):
        if not self.position:
            if (
                self.mad[0] >= self.params.long_threshold
                and self.data.close[0] >= 5
            ):
                self.buy()
            elif (
                self.mad[0] <= self.params.short_threshold
                and self.data.close[0] >= 5
            ):
                self.sell()
        elif self.position.size > 0 and self.mad[0] < self.params.long_threshold:
            self.close()
        elif self.position.size < 0 and self.mad[0] > self.params.short_threshold:
            self.close()

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    data = bt.feeds.GenericCSVData(
        dataname='your-data-file.csv',
        dtformat=('%Y-%m-%d'),
        openinterest=-1,
        timeframe=bt.TimeFrame.Days,
        compression=1,
    )
    cerebro.adddata(data)

    cerebro.addstrategy(MADStrategy)

    cerebro.broker.setcash(10000.0)
    cerebro.addsizer(bt.sizers.EqualWeight)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annualreturn')

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    result = cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    print('Sharpe Ratio:', result[0].analyzers.sharpe.get_analysis()['sharperatio'])
    print('Max Drawdown:', result[0].analyzers.drawdown.get_analysis()['max']['drawdown'])
    print('Annual Return:', result[0].analyzers.annualreturn.get_analysis())
```