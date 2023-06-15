<div align="center">
  <h1>Short-Term Momentum (Almost) Everywhere</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3340085)

## Trading rules

- Investment universe: 54 countries’ 10-year government bonds (refer to paper, pg. 8)
- Sort assets into quintiles based on past month return
- Long top quintile assets (highest returns from previous month)
- Short bottom quintile assets (lowest returns from previous month)
- Utilize equal weighting for assets
- Rebalance strategy on a monthly basis

## Statistics

- **Markets Traded:** Equities, bonds, bills, commodities, currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1961-2018
- **Annual Return:** 6.04%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.62
- **Annual Standard Deviation:** 9.69%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.feeds as btfeeds
import backtrader.indicators as btind
import math

class ShortTermMomentum(bt.Strategy):
    params = (
        ('n', 5),  # Number of quintiles
    )

    def __init__(self):
        self.returns = {}
        for d in self.datas:
            self.returns[d._name] = btind.PctChange(d.close, period=1)

    def next(self):
        rankings = sorted(
            self.datas, key=lambda d: self.returns[d._name][0], reverse=True
        )
        quintile_size = math.ceil(len(rankings) / self.params.n)
        long_assets = rankings[:quintile_size]
        short_assets = rankings[-quintile_size:]
        for i, d in enumerate(self.datas):
            if d in long_assets:
                target_weight = 1.0 / len(long_assets)
                self.order_target_percent(d, target_weight)
            elif d in short_assets:
                target_weight = -1.0 / len(short_assets)
                self.order_target_percent(d, target_weight)
            else:
                self.order_target_percent(d, 0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds
    for country_code in country_codes_list:  # Replace with the list of 54 countries' codes
        data_feed = btfeeds.YourDataFeed(dataname=country_code)  # Replace with your data feed
        cerebro.adddata(data_feed)

    # Set initial capital
    cerebro.broker.setcash(100000.0)

    # Add the strategy
    cerebro.addstrategy(ShortTermMomentum)

    # Set commissions
    cerebro.broker.setcommission(commission=0.001)

    # Set slippage
    cerebro.broker.set_slippage_fixed(0.001)

    # Run the strategy
    cerebro.run()

    # Plot the results
    cerebro.plot()
```

Note: Replace `country_codes_list` with the actual list of 54 countries’ codes and `btfeeds.YourDataFeed` with the data feed class you are using. Adjust the commissions and slippage as per your requirements.