<div align="center">
  <h1>Cross-Country Composite Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3240609)

## Trading rules

- Focus on the largest 20% of stocks on NYSE, NASDAQ, and AMEX
- Select top 20% stocks with best 12-month momentum (performance)
- Create an equally weighted portfolio of selected stocks
- Rebalance portfolio monthly
- Benchmark: equally weighted portfolio of largest 20% stocks on NYSE, NASDAQ, and AMEX

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1927-2010
- **Annual Return:** 14.3%
- **Maximum Drawdown:** -77.46%
- **Sharpe Ratio:** 0.49
- **Annual Standard Deviation:** 20.89%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.feeds as btfeeds
import datetime

class Momentum(bt.Strategy):
    params = (
        ('momentum_period', 252),
        ('rebalance_interval', 21),
        ('num_stocks', 0.2),
    )

    def __init__(self):
        self.add_timer(
            bt.timer.SESSION_END, monthdays=[1], monthcarry=True
        )  # Rebalance monthly

        self.inds = {}
        for d in self.datas:
            self.inds[d] = bt.indicators.ROC(d.close, period=self.params.momentum_period)

    def prenext(self):
        self.next()

    def notify_timer(self, timer, when, *args, **kwargs):
        if self._getminperstatus() < 0:
            return

        stocks = list(self.datas)
        stocks.sort(key=lambda d: self.inds[d][0], reverse=True)
        selected_stocks = stocks[:int(len(stocks) * self.params.num_stocks)]

        for d in self.datas:
            target = self.broker.getvalue() * (1 / len(selected_stocks)) if d in selected_stocks else 0
            self.order_target_value(d, target)

cerebro = bt.Cerebro()

# Add data for NYSE, NASDAQ, and AMEX stocks
# Replace 'NYSE.csv', 'NASDAQ.csv', and 'AMEX.csv' with appropriate files
for market in ['NYSE.csv', 'NASDAQ.csv', 'AMEX.csv']:
    data = btfeeds.GenericCSVData(
        dataname=market,
        fromdate=datetime.datetime(2000, 1, 1),
        todate=datetime.datetime(2020, 12, 31),
        dtformat=('%Y-%m-%d'),
        openinterest=-1,
        nullvalue=0.0,
        plot=False,
    )
    cerebro.adddata(data)

cerebro.broker.setcash(1000000.0)
cerebro.broker.setcommission(commission=0.001)  # 0.1% commission
cerebro.addstrategy(Momentum)

print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
results = cerebro.run()
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
cerebro.plot()
```

Make sure to replace ‘NYSE.csv’, ‘NASDAQ.csv’, and ‘AMEX.csv’ with the appropriate files containing the stock data for the mentioned exchanges. This code uses the Backtrader framework to implement the trading strategy as described.