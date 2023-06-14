<div align="center">
  <h1>Finding Yield in a 2% World</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2724737)

## Trading rules

- Bond selection from 30-country universe
- Monthly yield-based sorting
- Top 33% high-yield countries identified
- Equal-weighted portfolio allocation
- Monthly portfolio rebalancing

## Statistics

- **Markets Traded:** Bonds
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1950-2012
- **Annual Return:** 9.91%
- **Maximum Drawdown:** -24.74%
- **Sharpe Ratio:** 0.68
- **Annual Standard Deviation:** 8.63%

## Python code

### Backtrader

Here is the Python code for the trading rules using Backtrader:

```python
import backtrader as bt

class BondSelectionStrategy(bt.Strategy):
    def __init__(self):
        self.bond_universe = self.datas

    def next(self):
        # Sort bonds by yield (descending)
        sorted_bonds = sorted(self.bond_universe, key=lambda bond: bond.close[0], reverse=True)

        # Select the top 33% high-yield countries
        top_n = int(len(sorted_bonds) * 0.33)
        selected_bonds = sorted_bonds[:top_n]

        # Equal-weighted portfolio allocation
        weight = 1.0 / len(selected_bonds)

        # Rebalance the portfolio monthly
        for bond in self.bond_universe:
            if bond in selected_bonds:
                self.order_target_percent(bond, target=weight)
            else:
                self.order_target_percent(bond, target=0.0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add data feeds to cerebro for the 30-country bond universe
    # cerebro.adddata(...)
    cerebro.addstrategy(BondSelectionStrategy)
    cerebro.run()

```

This code defines a BondSelectionStrategy class that inherits from Backtrader’s Strategy class. The bond selection, sorting, and portfolio allocation are implemented in the `next` method, which is called at each step of the strategy. The strategy rebalances the portfolio monthly, as specified in the trading rules.