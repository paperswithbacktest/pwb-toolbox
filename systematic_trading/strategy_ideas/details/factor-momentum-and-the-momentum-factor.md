<div align="center">
  <h1>Factor Momentum and the Momentum Factor</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3014521)

## Trading rules

- Use French decile portfolios (Kenneth French data library) or construct custom portfolios
- Investment universe: AMEX, NYSE, and NASDAQ stocks
- Monthly stock sorting based on performance between t-2 and t-12 months (momentum with a skipped month)
- Value-weight stocks in each decile
- Track equity curve of simple momentum strategy without a filter
- Apply a 24-month moving average filter to the equity curve
- Go long on stocks in the highest momentum decile only if previous month’s equity curve point is above the 24-month average

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1960-2011
- **Annual Return:** 21.58%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.94
- **Annual Standard Deviation:** 18.69%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class MomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 11),
        ('ranking_period', 1),
        ('moving_average_period', 24),
    )

    def __init__(self):
        self.momentum = {}
        for d in self.datas:
            self.momentum[d] = bt.indicators.Momentum(d.close, period=self.params.momentum_period)

        self.equity_curve = bt.indicators.SimpleMovingAverage(self._owner._value, period=self.params.moving_average_period)

    def next(self):
        rankings = sorted(self.datas, key=lambda x: self.momentum[x][0])
        top_decile = rankings[-10:]

        for d in self.datas:
            if d in top_decile and self.equity_curve[-1] > self.equity_curve[-2]:
                self.order_target_percent(d, target=1.0 / len(top_decile))
            else:
                self.order_target_percent(d, target=0.0)

def get_data(stock_pool):
    datafeeds = []
    for stock in stock_pool:
        data = bt.feeds.GenericCSVData(
            dataname=f'path/to/{stock}.csv',
            fromdate=datetime.datetime(1960, 1, 1),
            todate=datetime.datetime(2011, 12, 31),
            dtformat=('%Y-%m-%d'),
            openinterest=-1,
            nullvalue=0.0,
            plot=False,
        )
        datafeeds.append(data)
    return datafeeds

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    stock_pool = ['stock1', 'stock2', 'stock3']  # Replace with actual stock symbols
    datafeeds = get_data(stock_pool)

    for data in datafeeds:
        cerebro.adddata(data)

    cerebro.addstrategy(MomentumStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
    print(f'Final Portfolio Value: {cerebro.broker.getvalue()}')
```