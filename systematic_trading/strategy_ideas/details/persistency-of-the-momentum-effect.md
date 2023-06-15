<div align="center">
  <h1>Persistency of the Momentum Effect</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2652592)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ stocks with at least 7 months of price data on CRSP database
- Zero-investment portfolio creation at month-end (t)
    - Long stocks in top decile for returns in both t-7 to t-1 and t-6 to t periods
    - Short stocks in bottom decile for returns in both t-7 to t-1 and t-6 to t periods
- Equal weighting for stocks in the portfolio
- Holding period: 6 months, no rebalancing
- One-month skip between formation and holding periods

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1980-2011
- **Annual Return:** 16.08%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.48
- **Annual Standard Deviation:** 25.33%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class ConsistentMomentumStrategy(bt.Strategy):
    params = (
        ('lookback1', 7),
        ('lookback2', 6),
        ('holding_period', 6),
        ('skip_period', 1),
        ('decile', 0.1),
    )

    def __init__(self):
        self.rank_data = []

    def next(self):
        if len(self.data) < self.params.lookback1 + self.params.holding_period:
            return

        if self.data.datetime.date(0).month == self.data.datetime.date(-1).month:
            return

        if self.data.datetime.date(0).month != self.data.datetime.date(-self.params.holding_period).month:
            return

        self.rank_data = []
        for data in self.datas:
            if len(data) >= self.params.lookback1 + self.params.holding_period:
                ret1 = (data.close[0] - data.close[-self.params.lookback1]) / data.close[-self.params.lookback1]
                ret2 = (data.close[0] - data.close[-self.params.lookback2]) / data.close[-self.params.lookback2]
                self.rank_data.append((data, ret1, ret2))

        sorted_data = sorted(self.rank_data, key=lambda x: (x[1], x[2]), reverse=True)
        top_decile = int(len(sorted_data) * self.params.decile)
        bottom_decile = len(sorted_data) - top_decile

        for i in range(top_decile):
            self.order_target_percent(sorted_data[i][0], target=1 / top_decile)

        for i in range(bottom_decile):
            self.order_target_percent(sorted_data[-(i + 1)][0], target=-1 / bottom_decile)

        self.rank_data = []

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add your data feeds for NYSE, AMEX, and NASDAQ stocks
    # cerebro.adddata(feed)

    cerebro.addstrategy(ConsistentMomentumStrategy)
    cerebro.run()
```

Remember to replace the comment `# cerebro.adddata(feed)` with your data feeds for NYSE, AMEX, and NASDAQ stocks with at least 7 months of price data on the CRSP database.