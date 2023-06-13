<div align="center">
  <h1>Don’t Get Carried Away: Uncovering Macro Characteristics in Carry Portfolios</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3269361)

## Trading rules

- Investment universe: 13 country equity index futures, 19 FX forward contracts, 23 commodities futures, 10 government bonds contracts
- Four carry types: equity carry, currency carry, commodity carry, bond carry
    - Currency carry: long high carry currencies, short low carry currencies; carry = local interest rate
    - Equity carry: expected dividend yield - risk-free rate
    - Commodity carry: convenience yield - storage costs; compare nearest to maturity futures contract with longer-dated contract
    - Bond carry: yield to maturity - short-term risk-free rate
- Carry portfolios: long high-carry, short low-carry; weighted by carry rank; monthly rebalancing
- Diversified carry strategy: equal-volatility-weighted average of carry portfolio returns across asset classes

## Statistics

- **Markets Traded:** Bonds, commodities, currencies, equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1991-2011
- **Annual Return:** 6.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.41
- **Annual Standard Deviation:** 4.9%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class CarryStrategy(bt.Strategy):
    def __init__(self):
        self.equity_carry = []
        self.currency_carry = []
        self.commodity_carry = []
        self.bond_carry = []

    def next(self):
        # Rebalance monthly
        if self.datas[0].datetime.date(0).month != self.datas[0].datetime.date(-1).month:
            # Update carry values
            self.update_carry_values()

            # Rank and get long/short positions for each carry type
            long_short_equities = self.rank_carry(self.equity_carry)
            long_short_currencies = self.rank_carry(self.currency_carry)
            long_short_commodities = self.rank_carry(self.commodity_carry)
            long_short_bonds = self.rank_carry(self.bond_carry)

            # Equal-volatility-weighted average of carry portfolio returns
            diversified_carry_weights = self.calculate_diversified_carry_weights()

            # Allocate weights to long/short positions
            self.allocate_weights(long_short_equities, diversified_carry_weights[0])
            self.allocate_weights(long_short_currencies, diversified_carry_weights[1])
            self.allocate_weights(long_short_commodities, diversified_carry_weights[2])
            self.allocate_weights(long_short_bonds, diversified_carry_weights[3])

    def update_carry_values(self):
        # Update carry values for each asset class (equity, currency, commodity, bond)
        pass

    def rank_carry(self, carry_list):
        # Rank carry values and return long/short positions
        pass

    def calculate_diversified_carry_weights(self):
        # Calculate equal-volatility-weighted average of carry portfolio returns
        pass

    def allocate_weights(self, long_short_positions, weight):
        # Allocate weights to long/short positions for each carry type
        pass

# Instantiate Cerebro, add strategy, data, and execute
cerebro = bt.Cerebro()
cerebro.addstrategy(CarryStrategy)

# Add data for 13 country equity index futures, 19 FX forward contracts, 23 commodities futures, and 10 government bonds contracts
# ...

cerebro.run()
```

Please note that this code serves as a basic outline for the CarryStrategy. You will need to implement the methods for updating carry values, ranking carry, calculating diversified carry weights, and allocating weights according to your specific data and requirements. You will also need to add the relevant data feeds for the asset classes.