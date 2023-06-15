<div align="center">
  <h1>Speculative Pressure</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3279425)

## Trading rules

- Investment universe: 27 commodity futures (12 agricultural, 5 energy, 4 livestock, 5 metal, 1 lumber)
- Hold nearest contract until 1 month before maturity, then roll to second nearest
- Exclude bottom 25% of commodities with lowest average open interest from previous weeks
- Calculate hedging pressure: long positions / total non-commercial positions from previous week
- Utilize Commitment of Traders report data
- Long positions: top 20% contracts with highest speculator hedging pressure (R weeks)
- Short positions: top 20% contracts with lowest speculator hedging pressure (R weeks)
- Hold positions for H weeks before forming new long-short portfolios
- 4 ranking periods (R): 4, 13, 26, 52 weeks
- 16 long-short portfolios created and rebalanced

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1992-2010
- **Annual Return:** 8.35%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.25
- **Annual Standard Deviation:** 17.17%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class CommodityStrategy(bt.Strategy):
    params = (
        ('ranking_periods', [4, 13, 26, 52]),
        ('holding_weeks', 1),
    )

    def __init__(self):
        self.cot_data = self.load_cot_data()
        self.portfolios = []

    def load_cot_data(self):
        # Load Commitment of Traders (COT) data
        # Replace this function with your COT data loading process
        pass

    def next(self):
        if len(self.datas) < max(self.params.ranking_periods) * 7:
            return

        if self.datetime.weekday() == 0:  # Monday (start of the week)
            current_date = self.datetime.date(0)
            one_month_before = current_date - pd.DateOffset(months=1)

            # Roll contracts and exclude bottom 25% with lowest open interest
            for d in self.datas:
                if d.contract_date < one_month_before:
                    # Replace d with second nearest contract
                    pass

            if len(self) % (self.params.holding_weeks * 7) == 0:
                # Calculate hedging pressure for each data
                hedging_pressures = []
                for d in self.datas:
                    cot_data = self.cot_data.loc[
                        self.cot_data['date'] == current_date - pd.DateOffset(weeks=1),
                        d.symbol
                    ]
                    long_positions = cot_data['long_positions']
                    total_positions = cot_data['total_positions']
                    hedging_pressure = long_positions / total_positions
                    hedging_pressures.append((d, hedging_pressure))

                # Rank and select contracts for long and short positions
                hedging_pressures.sort(key=lambda x: x[1])
                n = len(hedging_pressures)
                long_contracts = [x[0] for x in hedging_pressures[-int(n * 0.2):]]
                short_contracts = [x[0] for x in hedging_pressures[:int(n * 0.2)]]

                # Create and rebalance portfolios
                self.portfolios = []
                for R in self.params.ranking_periods:
                    long_short_portfolios = [
                        (long, self.broker.getposition(long).size)
                        for long in long_contracts[-int(R * 0.2):]
                    ] + [
                        (short, -self.broker.getposition(short).size)
                        for short in short_contracts[:int(R * 0.2)]
                    ]
                    self.portfolios.append(long_short_portfolios)

                # Execute trades
                for portfolio in self.portfolios:
                    for data, target_size in portfolio:
                        self.order_target_size(data, target_size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for each commodity future contract
    # Replace this part with your data loading process

    cerebro.addstrategy(CommodityStrategy)
    cerebro.run()
```

Note: This code provides an outline for the strategy implementation, and you will need to replace or modify the data loading process and adapt the code to your specific data sources for commodity futures and Commitment of Traders (COT) report data.