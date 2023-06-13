<div align="center">
  <h1>Empirical Evidence on the Currency Carry Trade, 1900-2012</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2060207)

## Trading rules

Forex Carry Trade Strategy: Key Steps

Apologies for the confusion earlier. Here are the key steps for the Forex Carry Trade Strategy:

- Identify high-yielding and low-yielding currencies
- Perform fundamental analysis to assess economic conditions
- Choose a suitable currency pair to trade
- Determine the optimal trade size
- Open a long position on the high-yielding currency
- Open a short position on the low-yielding currency
- Monitor and manage the trade (adjust stop losses, take profits)
- Close positions when the interest rate differential narrows or economic conditions change

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1989-2010
- **Annual Return:** 7.49%
- **Maximum Drawdown:** -34.55%
- **Sharpe Ratio:** 0.77
- **Annual Standard Deviation:** 9.7%

## Python code

### Backtrader

```python
import backtrader as bt

class ForexCarryTradeStrategy(bt.Strategy):
    def __init__(self):
        self.high_yielding = None
        self.low_yielding = None

    def next(self):
        if not self.high_yielding or not self.low_yielding:
            return

        size = self.calculate_trade_size()

        # Go long on the high-yielding currency
        self.buy(data=self.high_yielding, size=size)

        # Go short on the low-yielding currency
        self.sell(data=self.low_yielding, size=size)

    def calculate_trade_size(self):
        # Implement your logic to determine the optimal trade size
        return 1

    def perform_fundamental_analysis(self):
        # Implement your logic to assess economic conditions and choose a suitable currency pair
        pass

    def monitor_and_manage_trade(self):
        # Implement your logic to adjust stop losses and take profits
        pass

    def check_interest_rate_differential(self):
        # Implement your logic to check if the interest rate differential narrows or economic conditions change
        return False

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, {order.executed.price}')
            elif order.issell():
                self.log(f'SELL EXECUTED, {order.executed.price}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add your data feeds for high-yielding and low-yielding currencies
    # cerebro.adddata(data_high_yielding)
    # cerebro.adddata(data_low_yielding)

    cerebro.addstrategy(ForexCarryTradeStrategy)
    cerebro.broker.setcash(100000.0)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

This is a basic implementation of the Forex Carry Trade Strategy using the Backtrader library. You’ll need to implement your own logic for choosing currency pairs, determining trade size, managing the trade, and checking interest rate differentials.