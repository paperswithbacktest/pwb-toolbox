<div align="center">
  <h1>The Tactical and Strategic Value of Commodity Futures</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=650923)

## Trading rules

- This strategy buys the 20% of commodities with the highest roll-returns
- This strategy also shorts the 20% of commodities with the lowest roll-returns
- Long-short positions are held for one month
- Contracts in each quintile are equally-weighted
- The investment universe is all commodity futures contracts

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** monthly
- **Backtest period:** 1979-2004
- **Annual Return:** 11.73%
- **Maximum Drawdown:** -57.53%
- **Sharpe Ratio:** 0.49
- **Annual Standard Deviation:** 23.84%

## Python code

### Backtrader

```python
import backtrader as bt

class RollRankStrategy(bt.Strategy):
    def __init__(self):
        self.quintiles = 5
        self.contracts_per_quintile = len(self.datas) // self.quintiles
        self.roll_period = 30
        self.num_longs_shorts = self.contracts_per_quintile // 5

    def next(self):
        roll_returns = [d.close[-1] / d(-self.roll_period).close[0] for d in self.datas]
        ranks = sorted(range(len(roll_returns)), key=lambda x: roll_returns[x])
        for i in ranks[-self.num_longs_shorts:]:
            self.buy(self.datas[i], size=1/self.num_longs_shorts)
        for i in ranks[:self.num_longs_shorts]:
            self.sell(self.datas[i], size=1/self.num_longs_shorts)
```

Note: This is just an example, and the code may need to be adjusted based on the specifics of the commodity futures contracts being traded.