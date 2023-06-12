<div align="center">
  <h1>A Smiling Bear in the Equity Options Market and the Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2632763)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ-listed stocks with liquid options and available implied volatility data from OptionMetrics database
- Calculate IV convexity using the formula: IV convexity = IVput(Δ = -0.2) + IVput(Δ = -0.8) − 2 x IVcall(Δ = 0.5)
- On the last trading day of each month, sort stocks into quintiles (Q1-Q5) based on IV convexity
- Go long on the lowest IV convexity quintile (portfolio Q1) and short on the highest IV convexity quintile (portfolio Q5)
- Use value-weighted stocks in the portfolios
- Rebalance portfolios monthly
- Hold portfolios for one month

## Statistics

- **Markets Traded:** equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2000-2013
- **Annual Return:** 14.44%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.05
- **Annual Standard Deviation:** 9.99%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class IVConvexity(bt.Strategy):
    def __init__(self):
        self.iv_convexity = {}

    def next(self):
        if self.data.datetime.date(ago=0).month != self.data.datetime.date(ago=-1).month:
            for data in self.datas:
                iv_put_1 = data.iv_put(-0.2)
                iv_put_2 = data.iv_put(-0.8)
                iv_call = data.iv_call(0.5)
                iv_convexity = iv_put_1 + iv_put_2 - 2 * iv_call
                self.iv_convexity[data._name] = iv_convexity

            sorted_by_iv = sorted(self.iv_convexity.items(), key=lambda x: x[1])
            quintile_size = len(sorted_by_iv) // 5
            long_stocks = [stock[0] for stock in sorted_by_iv[:quintile_size]]
            short_stocks = [stock[0] for stock in sorted_by_iv[-quintile_size:]]

            for stock in long_stocks:
                if self.getposition(data=self.getdatabyname(stock)).size == 0:
                    self.order_target_percent(data=self.getdatabyname(stock), target=1 / len(long_stocks))

            for stock in short_stocks:
                if self.getposition(data=self.getdatabyname(stock)).size == 0:
                    self.order_target_percent(data=self.getdatabyname(stock), target=-1 / len(short_stocks))

            for data in self.datas:
                if data._name not in long_stocks + short_stocks:
                    self.close(data=data)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add data feeds for stocks with liquid options and available implied volatility data
    # Data should include columns for IV put and IV call values
    cerebro.adddata(...)  # Replace ... with your data feeds
    cerebro.addstrategy(IVConvexity)
    cerebro.run()

```

Please note that this code assumes you have the required implied volatility data in your data feeds. You will need to adjust the `iv_put` and `iv_call` functions to work with your specific data feeds.