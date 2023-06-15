<div align="center">
  <h1>Related Securities and the Cross-Section of Stock Return Momentum: Evidence From Credit Default Swaps (CDS)</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2819774)

## Trading rules

- Investment universe: NYSE, AMEX, NASDAQ-listed firms with available stock returns data (CRSP) and CDS contract data (Markit Group)
- Two signals: Joint momentum and disjoint contrarian
    - Joint momentum:
        - Sort stocks and CDS into quintiles based on past 12-month returns (excluding the most recent month) and past 4-month returns
        - Buy (sell) firms in the top (bottom) quintile for both instruments
    - Disjoint contrarian:
        - Buy (sell) firms in the bottom (top) quintile for stocks and simultaneously in the top (bottom) quintile for CDS contracts
- Strategy is value-weighted, using firms’ market capitalization for long and short positions
- Holding period: One month

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 2003-2014
- **Annual Return:** 16.86%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.9
- **Annual Standard Deviation:** 14.29%

## Python code

### Backtrader

```python
import backtrader as bt

class CombinedStrategy(bt.Strategy):
    params = (
        ("momentum_period_stock", 12),
        ("momentum_period_cds", 4),
        ("skip_period", 1),
        ("quintile", 0.2),
        ("holding_period", 21),
    )

    def __init__(self):
        self.stock_returns = {}
        self.cds_returns = {}
        self.stock_weights = {}
        self.signals = {}

    def next(self):
        if len(self.data) <= self.params.momentum_period_stock:
            return

        for d in self.datas:
            self.stock_returns[d] = d.close.get(size=self.params.momentum_period_stock)[-self.params.skip_period]
            self.cds_returns[d] = d.cds.get(size=self.params.momentum_period_cds)
            self.stock_weights[d] = d.market_cap / sum([d_.market_cap for d_ in self.datas])

        stock_quintiles = self.get_quintiles(self.stock_returns)
        cds_quintiles = self.get_quintiles(self.cds_returns)

        for d in self.datas:
            stock_signal = (stock_quintiles[d] == 1) - (stock_quintiles[d] == 5)
            cds_signal = (cds_quintiles[d] == 1) - (cds_quintiles[d] == 5)
            joint_momentum_signal = stock_signal * cds_signal
            disjoint_contrarian_signal = -stock_signal * (cds_signal * -1)
            self.signals[d] = joint_momentum_signal + disjoint_contrarian_signal

        for i, d in enumerate(self.datas):
            if self.signals[d] == 1:
                self.order_target_percent(d, target=self.stock_weights[d])
            elif self.signals[d] == -1:
                self.order_target_percent(d, target=-self.stock_weights[d])
            else:
                self.order_target_percent(d, target=0)

            if i % self.params.holding_period == 0:
                self.broker.cancel(self.signals[d])

    def get_quintiles(self, values):
        sorted_values = sorted(values.items(), key=lambda x: x[1])
        total = len(sorted_values)
        quintiles = {k: int((i / total) // self.params.quintile) + 1 for i, (k, v) in enumerate(sorted_values)}
        return quintiles

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Add your data feeds here
    # cerebro.adddata(...)
    # cerebro.adddata(...)

    cerebro.addstrategy(CombinedStrategy)
    cerebro.run()
```

Note that this code is just a starting point and assumes you have the necessary data feeds (including CDS and market capitalization data) set up properly. You may need to adjust the code to fit your specific data sources and feed formats.