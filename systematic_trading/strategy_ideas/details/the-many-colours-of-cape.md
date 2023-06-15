<div align="center">
  <h1>The Many Colours of CAPE</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3258404)

## Trading rules

- Determine investment universe: 10 sector-specific ETFs
- Monthly calculations: Compute CAPE and relative CAPE ratios for each sector
- Sector selection: Identify 5 sectors with the lowest relative CAPE values
- Momentum filter: Exclude the sector with the weakest 12-month momentum
- Portfolio composition: Allocate equal weights to the remaining 4 sectors
- Rebalancing: Adjust portfolio monthly to maintain equal weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2002-2017
- **Annual Return:** 14.23%
- **Maximum Drawdown:** -43.54%
- **Sharpe Ratio:** 0.79
- **Annual Standard Deviation:** 17.98%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class CAPEMomentum(bt.Strategy):
    params = (
        ('num_sectors', 10),
        ('low_cape_sectors', 5),
        ('momentum_period', 12),
    )

    def __init__(self):
        self.sectors = self.datas
        self.cape = {}
        self.relative_cape = {}
        self.momentum = {}

    def next(self):
        # Calculate CAPE and relative CAPE for each sector
        for sector in self.sectors:
            self.cape[sector] = self.calculate_cape(sector)
            self.relative_cape[sector] = self.cape[sector] / sum(self.cape.values())

        # Select 5 sectors with the lowest relative CAPE values
        selected_sectors = sorted(self.relative_cape, key=self.relative_cape.get)[:self.params.low_cape_sectors]

        # Calculate 12-month momentum for the selected sectors
        for sector in selected_sectors:
            self.momentum[sector] = sector.close[0] / sector.close[-self.params.momentum_period] - 1

        # Exclude the sector with the weakest 12-month momentum
        weakest_sector = min(self.momentum, key=self.momentum.get)
        selected_sectors.remove(weakest_sector)

        # Calculate equal weights for the remaining 4 sectors
        weights = {sector: 1/len(selected_sectors) for sector in selected_sectors}

        # Rebalance the portfolio
        for sector, weight in weights.items():
            target_value = self.broker.getvalue() * weight
            current_value = self.broker.getposition(sector).size * sector.close[0]
            size_diff = (target_value - current_value) / sector.close[0]

            if size_diff > 0:
                self.buy(sector, size=size_diff)
            elif size_diff < 0:
                self.sell(sector, size=-size_diff)

    def calculate_cape(self, sector):
        # Compute CAPE for a given sector (dummy calculation for example purposes)
        return sector.close[0] / sector.close[-1]

# Backtest configuration
cerebro = bt.Cerebro()

# Add ETF data for each sector (replace with actual data)
for sector_ETF in ['ETF1', 'ETF2', 'ETF3', 'ETF4', 'ETF5', 'ETF6', 'ETF7', 'ETF8', 'ETF9', 'ETF10']:
    data = pd.read_csv(f'{sector_ETF}.csv', index_col='Date', parse_dates=True)
    cerebro.adddata(bt.feeds.PandasData(dataname=data, name=sector_ETF))

cerebro.addstrategy(CAPEMomentum)
cerebro.broker.setcash(100000)
cerebro.broker.set_coc(True)

# Run the backtest
results = cerebro.run()
```

Note that this example assumes you have historical data for each sector-specific ETF in CSV files named ‘ETF1.csv’, ‘ETF2.csv’, etc. Replace the data loading part with the actual data source you have. Also, replace the `calculate_cape()` function with the actual CAPE calculation for each sector.