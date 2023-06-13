<div align="center">
  <h1>Another Look at Trading Costs and Short-Term Reversal Profits</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1605049)

## Trading rules

- Investment universe: Top 100 companies by market capitalization
- Go long: 10 stocks with lowest performance in previous month
- Go short: 10 stocks with highest performance in previous month
- Rebalance portfolio: Weekly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1990-2009
- **Annual Return:** 16.25%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.8
- **Annual Standard Deviation:** 6.8%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class ShortTermReversalStrategy(bt.Strategy):
    params = (
        ('num_long', 10),
        ('num_short', 10),
        ('rebalance_frequency', 5),  # Rebalance every week (5 trading days)
    )

    def __init__(self):
        self.add_timer(
            bt.timer.SESSION_END,
            monthdays=[1],
            monthcarry=True,
        )

    def notify_timer(self, timer, when, *args, **kwargs):
        if self._getminperstatus() < 0:
            return
        if self.data.datetime.date(ago=0) == self.data.datetime.date(-self.p.rebalance_frequency):
            self.rebalance()

    def rebalance(self):
        # Sort stocks by performance over the last month
        stocks_performance = sorted(
            self.datas,
            key=lambda data: (data.close[0] - data.close[-20]) / data.close[-20],
            reverse=True,
        )

        # Close all positions
        for data in self.datas:
            self.close(data=data)

        # Enter new long positions
        for data in stocks_performance[-self.p.num_long:]:
            self.buy(data=data, exectype=bt.Order.Market)

        # Enter new short positions
        for data in stocks_performance[:self.p.num_short]:
            self.sell(data=data, exectype=bt.Order.Market)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Load top 100 stocks by market cap (datafeeds should be pre-filtered)
    for stock_data in top_100_stocks_data:
        cerebro.adddata(stock_data)

    cerebro.addstrategy(ShortTermReversalStrategy)
    cerebro.run()
```

Make sure to replace `top_100_stocks_data` with your own list of data feeds for the top 100 companies by market capitalization.