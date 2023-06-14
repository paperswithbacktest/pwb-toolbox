<div align="center">
  <h1>Industry Momentum: The Role of Time-Varying Factor Exposures and Market Conditions</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2650378)

## Trading rules

- Utilize 10 sector ETFs
- Select top 3 ETFs with highest 12-month momentum
- Allocate equal weight to chosen 3 ETFs
- Maintain holdings for 1 month
- Rebalance portfolio monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1928-2009
- **Annual Return:** 13.94%
- **Maximum Drawdown:** -71.29%
- **Sharpe Ratio:** 0.54
- **Annual Standard Deviation:** 18.38%

## Python code

### Backtrader

```python
import backtrader as bt

class MomentumRank(bt.Strategy):
    params = dict(
        momentum_period=252,  # 12-month momentum period
        num_etfs=10,  # 10 sector ETFs
        top_n=3,  # Select top 3 ETFs with highest momentum
        rebalance_interval=21  # Rebalance monthly (assuming 21 trading days per month)
    )

    def __init__(self):
        self.inds = {}
        self.execution_day = 0

        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['momentum'] = bt.indicators.Momentum(d.close, period=self.p.momentum_period)

    def next(self):
        if self.inds[self.data]['momentum'].lines[0][-1] == 0.0:
            return

        if self.execution_day > 0:
            self.execution_day -= 1
            return

        rankings = list(self.datas)
        rankings.sort(key=lambda x: self.inds[x]['momentum'][0], reverse=True)
        top_stocks = rankings[:self.p.top_n]
        target_weights = dict()

        for d in top_stocks:
            target_weights[d] = 1.0 / self.p.top_n

        self.rebalance_portfolio(target_weights)
        self.execution_day = self.p.rebalance_interval

    def rebalance_portfolio(self, target_weights):
        current_value = self.broker.getvalue()

        for d, target_weight in target_weights.items():
            current_position = self.getposition(d).size
            target_position = int(current_value * target_weight / d.close[0])
            delta_position = target_position - current_position

            if delta_position > 0:
                self.buy(data=d, size=delta_position)
            elif delta_position < 0:
                self.sell(data=d, size=-delta_position)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, Size: %d, Price: %.2f, Cost: %.2f' %
                         (order.executed.size, order.executed.price, order.executed.value))
            elif order.issell():
                self.log('SELL EXECUTED, Size: %d, Price: %.2f, Cost: %.2f' %
                         (order.executed.size, order.executed.price, order.executed.value))
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

cerebro = bt.Cerebro()

# Add your 10 ETF data feeds here
# Example: cerebro.adddata(bt.feeds.YahooFinanceData(dataname='SPY', fromdate=start_date, todate=end_date))

cerebro.broker.setcash(100000.0)
cerebro.addstrategy(MomentumRank)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

results = cerebro.run()
strat = results[0]

print('Sharpe Ratio:', strat.analyzers.sharpe.get_analysis())
print('Returns:', strat.analyzers.returns.get_analysis())
print('Drawdown:', strat.analyzers.drawdown.get_analysis())

cerebro.plot()
```