<div align="center">
  <h1>Momentum, Contrarian, and the January Seasonality</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1663686)

## Trading rules

- Investment universe: NYSE and AMEX-listed stocks (excluding closed-end funds, REITs, ADRs, and foreign stocks)
- Monthly ranking: Sort stocks into ten deciles based on compounded returns from months t-13 to t-60
- Long position: Invest in bottom performance decile (past losers)
- Short position: Invest in top performance decile (past winners)
- Portfolio weighting: Value-weighted (reduces impact of smaller stocks)
- Timing: Invest in this strategy only in January

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1926-2009
- **Annual Return:** 11.27%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.86
- **Annual Standard Deviation:** 12.7%

## Python code

### Backtrader

```python
import backtrader as bt
from datetime import datetime

class JanuaryEffectStrategy(bt.Strategy):
    def __init__(self):
        self.rank_period_start = -60
        self.rank_period_end = -13

    def next(self):
        if self.datetime.month[0] != 1:
            return  # Invest only in January

        # Ranking stocks based on compounded returns
        stocks_returns = []
        for d in self.datas:
            if d._name in ['NYSE', 'AMEX']:
                continue  # Skip exchange symbols

            compounded_return = (d.close[self.rank_period_start] / d.close[self.rank_period_end]) - 1
            stocks_returns.append((d, compounded_return))

        stocks_returns.sort(key=lambda x: x[1])

        # Split into deciles
        deciles = [stocks_returns[i::10] for i in range(10)]

        # Get top and bottom deciles
        top_decile = deciles[-1]
        bottom_decile = deciles[0]

        # Calculate the value-weighted portfolio
        total_value = sum([stock[0].close[0] * stock[0].volume[0] for stock in stocks_returns])

        # Invest in top and bottom deciles
        for stock, _ in top_decile:
            weight = (stock.close[0] * stock.volume[0]) / total_value
            self.sell(data=stock, size=weight)

        for stock, _ in bottom_decile:
            weight = (stock.close[0] * stock.volume[0]) / total_value
            self.buy(data=stock, size=weight)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds (exchange and stocks) to the strategy
    # ... (code for loading data feeds)

    cerebro.addstrategy(JanuaryEffectStrategy)

    # Execute the strategy
    cerebro.run()
```

Note that this code snippet assumes that you have already loaded the necessary data feeds for the stocks and exchanges. You will need to replace the comment `# ... (code for loading data feeds)` with your own code to load these data feeds before running the strategy.