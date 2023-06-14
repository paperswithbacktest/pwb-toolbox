<div align="center">
  <h1>Lumber: Worth Its Weight in Gold Offense and Defense in Active Portfolio Management</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2604248)

## Trading rules

- Compare Lumber vs. Gold performance over the past 13 weeks
- If Lumber outperforms Gold:
    - Adopt an aggressive portfolio stance
    - Hold small cap equities for the following week
- If Gold outperforms Lumber:
    - Adopt a defensive portfolio stance
    - Hold treasury bonds for the following week
- Reassess signal weekly
- Adjust portfolio only when Lumber-Gold leadership shifts

## Statistics

- **Markets Traded:** Bonds, equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1986-2015
- **Annual Return:** 13.9%
- **Maximum Drawdown:** -20.8%
- **Sharpe Ratio:** 0.84
- **Annual Standard Deviation:** 11.8%

## Python code

### Backtrader

```python
import backtrader as bt

class LumberGoldStrategy(bt.Strategy):
    params = (
        ('lookback_period', 13),
    )

    def __init__(self):
        self.lumber = self.getdatabyname('Lumber')
        self.gold = self.getdatabyname('Gold')
        self.small_cap = self.getdatabyname('SmallCap')
        self.treasury_bonds = self.getdatabyname('TreasuryBonds')

    def next(self):
        lumber_performance = self.lumber.close[0] / self.lumber.close[-self.params.lookback_period]
        gold_performance = self.gold.close[0] / self.gold.close[-self.params.lookback_period]

        if lumber_performance > gold_performance:
            self.order_target_percent(self.small_cap, target=1.0)
            self.order_target_percent(self.treasury_bonds, target=0.0)
        else:
            self.order_target_percent(self.small_cap, target=0.0)
            self.order_target_percent(self.treasury_bonds, target=1.0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    data_lumber = bt.feeds.YourDataFeed(dataname='Lumber')
    data_gold = bt.feeds.YourDataFeed(dataname='Gold')
    data_small_cap = bt.feeds.YourDataFeed(dataname='SmallCap')
    data_treasury_bonds = bt.feeds.YourDataFeed(dataname='TreasuryBonds')

    cerebro.adddata(data_lumber, name='Lumber')
    cerebro.adddata(data_gold, name='Gold')
    cerebro.adddata(data_small_cap, name='SmallCap')
    cerebro.adddata(data_treasury_bonds, name='TreasuryBonds')

    cerebro.addstrategy(LumberGoldStrategy)
    cerebro.run()
```

Replace `YourDataFeed` with the appropriate data feed class for your data source.