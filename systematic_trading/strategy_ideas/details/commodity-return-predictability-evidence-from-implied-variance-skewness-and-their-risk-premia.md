<div align="center">
  <h1>Commodity Return Predictability: Evidence from Implied Variance, Skewness and their Risk Premia</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3134310)

## Trading rules

- Investment universe: 8 commodities (agricultural: corn, soybeans, wheat; metal: copper, silver, gold; energy: oil, natural gas)
- Estimate implied skewness: Use Bakshi’s model-free approach with one-month options on futures contracts
- Build long-short portfolios:
    - Long position: Top 25% implied skewness commodities
    - Short position: Bottom 25% implied skewness commodities
- Portfolio composition: 2 long and 2 short commodity futures contracts, equal weights
- Portfolio formation: Daily, held for 21 overlapping business days (1 month)
- Rebalancing: Daily, maintain 1/21 portfolio weight

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Daily
- **Backtest period:** 2008-2016
- **Annual Return:** 17.21%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.47
- **Annual Standard Deviation:** 28%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class ImpliedSkewnessStrategy(bt.Strategy):
    params = (
        ('lookback', 21),
        ('rebalance_days', 1),
    )

    def __init__(self):
        self.rebalance_counter = 0

    def next(self):
        if self.rebalance_counter % self.params.rebalance_days == 0:
            self.rebalance_portfolio()
        self.rebalance_counter += 1

    def rebalance_portfolio(self):
        implied_skewness = []
        for d in self.getdatanames():
            skewness = self.calculate_implied_skewness(d)
            implied_skewness.append((d, skewness))

        implied_skewness.sort(key=lambda x: x[1], reverse=True)
        long_positions = implied_skewness[:2]
        short_positions = implied_skewness[-2:]

        target_weight = 1 / (2 * self.params.lookback)

        for data_name, _ in long_positions:
            data = self.getdatabyname(data_name)
            position_size = target_weight * self.broker.getvalue() / data.close[0]
            self.order_target_size(data, position_size)

        for data_name, _ in short_positions:
            data = self.getdatabyname(data_name)
            position_size = -target_weight * self.broker.getvalue() / data.close[0]
            self.order_target_size(data, position_size)

    def calculate_implied_skewness(self, data_name):
        # Implement Bakshi's model-free approach here
        # This function should return the implied skewness of the given data
        pass

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for the 8 commodities here
    # ...
    cerebro.adddata(data_feed, name='corn')
    cerebro.adddata(data_feed, name='soybeans')
    cerebro.adddata(data_feed, name='wheat')
    cerebro.adddata(data_feed, name='copper')
    cerebro.adddata(data_feed, name='silver')
    cerebro.adddata(data_feed, name='gold')
    cerebro.adddata(data_feed, name='oil')
    cerebro.adddata(data_feed, name='natural_gas')

    cerebro.addstrategy(ImpliedSkewnessStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

This is a basic template for the Implied Skewness Strategy in Backtrader. Note that you will need to implement the Bakshi’s model-free approach to calculate implied skewness and add the data feeds for the 8 commodities.