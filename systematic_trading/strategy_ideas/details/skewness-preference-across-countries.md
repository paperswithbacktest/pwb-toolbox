<div align="center">
  <h1>Skewness Preference Across Countries</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2606180)

## Trading rules

- Investment universe: 39 large markets from MSCI indexes (78 countries, in USD)
- Monthly skewness calculation: Based on past 24-months performance (formula on page 4 of source paper)
- Quintile sorting: Sort markets by skewness
- Long position: 100% in quintile with most negative skewness
- Short position: 100% in quintile with most positive skewness
- Rebalancing: Monthly, with equal weighting for markets

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1999-2014
- **Annual Return:** 13.76%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.54
- **Annual Standard Deviation:** 25.66%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from scipy.stats import skew

class SkewnessEffect(bt.Strategy):
    def __init__(self):
        self.month_counter = 0

    def next(self):
        self.month_counter += 1
        if self.month_counter % 20 != 0:
            return
        skewness_values = []
        for d in self.datas:
            past_24_months = np.array([d.close.get(-i) for i in range(1, 25)])
            monthly_returns = np.diff(past_24_months) / past_24_months[:-1]
            skewness_value = skew(monthly_returns)
            skewness_values.append((d, skewness_value))
        sorted_data = sorted(skewness_values, key=lambda x: x[1])
        quintile_size = len(sorted_data) // 5
        long_positions = sorted_data[:quintile_size]
        short_positions = sorted_data[-quintile_size:]
        for d, skewness_value in long_positions:
            self.order_target_percent(d, target=1 / quintile_size)
        for d, skewness_value in short_positions:
            self.order_target_percent(d, target=-1 / quintile_size)

cerebro = bt.Cerebro()

# Add data feeds for the 39 large markets
# ...

cerebro.addstrategy(SkewnessEffect)
cerebro.run()
```

Please note that this code snippet is only the strategy part and assumes that you have already added the data feeds for the 39 large markets to the `cerebro` object. You’ll need to add the data feeds and configure the `cerebro` object according to your specific data and requirements.