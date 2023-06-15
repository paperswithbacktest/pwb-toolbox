<div align="center">
  <h1>Profitable Price Impact: The Case of Convertible Bond Arbitrage</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3426914)

## Trading rules

- Focus on stocks from companies with convertible bonds marketed for over 1 day
- Exclude companies with historical stock prices below $5 per share
- Strategy: Short sell stock during convertible bond pricing day
- Rationale: Significant stock price decline typically occurs on bond pricing day

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1997-2016
- **Annual Return:** 2.25%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.5
- **Annual Standard Deviation:** 4.47%

## Python code

### Backtrader

```python
import backtrader as bt

class ConvertibleBondShort(bt.Strategy):
    params = (
        ('min_price', 5),
    )

    def __init__(self):
        self.order = None

    def next(self):
        for data in self.datas:
            if self.getposition(data).size == 0:
                if data.close[0] > self.params.min_price:
                    if self.is_bond_pricing_day(data):
                        self.sell(data=data)

    def is_bond_pricing_day(self, data):
        # You will need to implement the logic for identifying bond pricing day based on your data source
        # For example:
        if data._name in bond_pricing_days and self.datetime.date() == bond_pricing_days[data._name]:
            return True
        else:
            return False

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED: {order.executed.price}')
            elif order.issell():
                self.log(f'SELL EXECUTED: {order.executed.price}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

cerebro = bt.Cerebro()

# Add the stocks data to cerebro
# ...

# You will need to add the stock data and bond pricing day data based on your data source

cerebro.addstrategy(ConvertibleBondShort)
cerebro.broker.setcash(100000.0)
cerebro.addsizer(bt.sizers.PercentSizer, percents=10)

print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
cerebro.run()
print(f'Ending Portfolio Value: {cerebro.broker.getvalue():.2f}')
```

Please note that you will need to add your stock data and bond pricing day data based on your data source, and implement the `is_bond_pricing_day` method accordingly.