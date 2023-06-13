<div align="center">
  <h1>Commodity Option Implied Volatilities and the Expected Futures Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2939649)

## Trading rules

- Investment universe: 25 commodities
- Commodity groups: Sorted into 4 groups based on 30-day implied volatility de-trended by previous 12-month mean implied volatility
- Low group: Top 25% commodities with lowest volatilities
- High group: Top 25% commodities with highest volatilities
- Portfolio type: Long-short (buys from Low group, sells from High group)
- Portfolio weighting: Equally-weighted
- Rebalancing frequency: Monthly

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1991-2014
- **Annual Return:** 12.66%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.69
- **Annual Standard Deviation:** 18.48%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class ImpliedVolatilityStrategy(bt.Strategy):
    params = (
        ("n_commodities", 25),
        ("n_groups", 4),
        ("portfolio_frac", 0.25),
    )

    def __init__(self):
        self.commodities = self.datas

    def next(self):
        if self.datetime.date().month != self.datetime.date().day:
            return

        volatilities = []
        for data in self.commodities:
            historical_vol = data.get(size=252)
            last_30_days_vol = historical_vol[-30:]
            detrended_vol = last_30_days_vol - np.mean(historical_vol[:-30])
            volatilities.append((data, detrended_vol[-1]))

        volatilities.sort(key=lambda x: x[1])

        low_group = volatilities[:int(self.params.n_commodities * self.params.portfolio_frac)]
        high_group = volatilities[-int(self.params.n_commodities * self.params.portfolio_frac):]

        positions = {data: self.getposition(data).size for data in self.commodities}

        for data, _ in low_group:
            if positions[data] <= 0:
                self.order_target_percent(data, target=self.params.portfolio_frac / len(low_group))

        for data, _ in high_group:
            if positions[data] >= 0:
                self.order_target_percent(data, target=-self.params.portfolio_frac / len(high_group))

        for data, position in positions.items():
            if position != 0 and data not in [x[0] for x in low_group + high_group]:
                self.close(data)

cerebro = bt.Cerebro()

# Add data feeds for 25 commodities
# ...

cerebro.addstrategy(ImpliedVolatilityStrategy)
cerebro.run()
```