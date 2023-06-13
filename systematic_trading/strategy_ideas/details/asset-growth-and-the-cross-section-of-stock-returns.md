<div align="center">
  <h1>Asset Growth and the Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=760967)

## Trading rules

- Investment universe: Non-financial U.S. stocks (NYSE, AMEX, NASDAQ)
- Annual sorting: End of June
- Sorting criterion: Percentage change in total assets (previous year)
- Decile groups: Ten equal groups
- Long position: Low asset growth decile
- Short position: High asset growth decile
- Portfolio weighting: Equal
- Rebalancing frequency: Annually

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1968-2006
- **Annual Return:** 20.84%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.2
- **Annual Standard Deviation:** 14.07%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class AssetGrowthStrategy(bt.Strategy):
    def __init__(self):
        self.rebalance_month = 6
        self.rebalance_day = 30

    def next(self):
        if self.data.datetime.month[0] == self.rebalance_month and self.data.datetime.day[0] == self.rebalance_day:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        asset_growth_data = self.calculate_asset_growth()
        long_decile, short_decile = self.get_deciles(asset_growth_data)

        for stock in self.getdatanames():
            if stock in long_decile:
                self.order_target_percent(stock, target=1 / len(long_decile))
            elif stock in short_decile:
                self.order_target_percent(stock, target=-1 / len(short_decile))
            else:
                self.order_target_percent(stock, target=0)

    def calculate_asset_growth(self):
        asset_growth_data = {}
        for stock in self.getdatanames():
            data = self.getdatabyname(stock)
            prev_year_assets = data.total_assets[-252]
            current_assets = data.total_assets[0]
            asset_growth = (current_assets - prev_year_assets) / prev_year_assets
            asset_growth_data[stock] = asset_growth

        return asset_growth_data

    def get_deciles(self, asset_growth_data):
        sorted_growth_data = {k: v for k, v in sorted(asset_growth_data.items(), key=lambda item: item[1])}
        stock_count = len(sorted_growth_data)
        decile_size = stock_count // 10
        long_decile = list(sorted_growth_data.keys())[:decile_size]
        short_decile = list(sorted_growth_data.keys())[-decile_size:]

        return long_decile, short_decile

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(AssetGrowthStrategy)

    # Add your data feeds here
    # Example: cerebro.adddata(data_feed, name='stock_name')

    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    print('Initial Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Please note that this code assumes the data feeds you add to the `cerebro` object contain a `total_assets` line that represents the total assets for each stock in the universe. You should add your data feeds containing non-financial U.S. stocks (NYSE, AMEX, NASDAQ) with the required information in the `if __name__ == '__main__':` block.