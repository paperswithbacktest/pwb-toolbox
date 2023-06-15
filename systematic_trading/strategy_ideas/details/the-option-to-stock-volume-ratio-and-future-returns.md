<div align="center">
  <h1>The Option to Stock Volume Ratio and Future Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1624062)

## Trading rules

- Investment universe: US firms with liquid options (excluding CEFs, REITs, ADRs, and stocks priced below $1)
- Monthly calculation: Ratio of total option volume to total stock volume (O/S ratio)
    - Option volume: Total volume of option contracts across all strikes for options expiring within 30 trading days, starting 5 days after month end
    - Stock volume: Expressed in round lots of 100 for comparability with option contracts (each for 100 shares)
- Change in O/S ratio: Difference between current O/S ratio and the 6-month average O/S ratio, scaled by the average
- Monthly strategy:
    - Short position: Stocks with high O/S ratio change
    - Long position: Stocks with low O/S ratio change
- Portfolio management: Equal-weighted stocks, rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1996-2008
- **Annual Return:** 14.65%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.69
- **Annual Standard Deviation:** 15.5%

## Python code

### Backtrader

```python
import backtrader as bt

class OptionStockVolumeStrategy(bt.Strategy):
    params = (
        ('lookback', 6),
    )

    def __init__(self):
        self.os_ratio = {}
        self.os_ratio_change = {}

    def next(self):
        if len(self.data) <= self.params.lookback * 30:  # Wait for enough data
            return

        # Calculate the O/S ratio and change for each stock in the universe
        for d in self.datas:
            if self.getposition(d).size == 0:  # Exclude non-liquid stocks
                continue

            # Calculate the total option volume and total stock volume
            total_option_volume = sum([d.options.volume[i] for i in range(-30, -5)])
            total_stock_volume = sum([d.volume[i] // 100 for i in range(-30, -5)])

            # Calculate the O/S ratio and change
            os_ratio = total_option_volume / total_stock_volume
            os_ratio_avg = sum([self.os_ratio[d][i] for i in range(-6 * 30, 0)]) / (6 * 30)
            os_ratio_change = (os_ratio - os_ratio_avg) / os_ratio_avg

            self.os_ratio[d] = os_ratio
            self.os_ratio_change[d] = os_ratio_change

        # Sort stocks by O/S ratio change
        sorted_stocks = sorted(self.os_ratio_change, key=self.os_ratio_change.get)

        # Take long and short positions
        long_stocks = sorted_stocks[:len(sorted_stocks) // 2]
        short_stocks = sorted_stocks[-(len(sorted_stocks) // 2):]

        # Rebalance the portfolio
        for d in self.datas:
            if d in long_stocks:
                self.order_target_percent(d, target=1 / len(long_stocks))
            elif d in short_stocks:
                self.order_target_percent(d, target=-1 / len(short_stocks))
            else:
                self.order_target_percent(d, target=0)

cerebro = bt.Cerebro()
# Add the data feeds to cerebro
# ...

cerebro.addstrategy(OptionStockVolumeStrategy)
cerebro.run()
```

Please note that this code snippet assumes that the data feed for each stock contains both stock and option volume data. You may need to adjust or extend the data feed class to provide this information.