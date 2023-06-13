<div align="center">
  <h1>Diversity Investing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2706550)

## Trading rules

- Investment universe: Stocks listed on NYSE, AMEX, and NASDAQ with positive book value and at least 12 months of past returns in CRSP Database
- Firm biographical data source: Annual reports from EDGAR database (10-K, 10KSB, DEF 14A preferred)
- Diversity measure: Formulas (1) and (2) on page 7; D = 0 for firms with only one top executive
- Long position: Top quintile portfolio (firms with most diverse management teams)
- Short position: Bottom quintile portfolio (firms with most homogenous management teams)
- Rebalancing: Annually
- Holding period: One year
- Portfolio weighting: Value-weighted stocks

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 2002-2014
- **Annual Return:** 8.47%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.46
- **Annual Standard Deviation:** 9.81%

## Python code

### Backtrader

Here’s the Backtrader Python code for the given trading rules:

```python
import backtrader as bt

class DiversityStrategy(bt.Strategy):
    def __init__(self):
        self.diversity = self.datas[0].diversity

    def next(self):
        long_positions = []
        short_positions = []

        for data in self.datas:
            if len(data) < 12 or data.book_value[0] <= 0:
                continue

            if data.diversity[0] >= data.diversity.get(size=5)[0]:
                long_positions.append(data)
            elif data.diversity[0] <= data.diversity.get(size=5)[-1]:
                short_positions.append(data)

        long_weight = 1.0 / len(long_positions)
        short_weight = -1.0 / len(short_positions)

        for data in long_positions:
            self.order_target_percent(data=data, target=long_weight)

        for data in short_positions:
            self.order_target_percent(data=data, target=short_weight)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(DiversityStrategy)

    # Add data feeds from NYSE, AMEX, NASDAQ with biographical data from EDGAR (not shown)
    # Use the provided diversity measure as an additional data field (not shown)

    cerebro.run()
```

Please note that this code assumes you’ve already prepared the data feeds with the required information from the NYSE, AMEX, and NASDAQ, and have calculated the diversity measure according to the formulas given in your question.