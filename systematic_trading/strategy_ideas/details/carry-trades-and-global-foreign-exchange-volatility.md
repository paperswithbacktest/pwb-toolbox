<div align="center">
  <h1>Carry Trades and Global Foreign Exchange Volatility</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1342968)

## Trading rules

- Investment universe: 10 developed countries’ currencies (Australia, Canada, Denmark, Euro area, Japan, New Zealand, Norway, Sweden, Switzerland, UK)
- Calculate FX volatility measure: Absolute daily log returns for each currency, averaged to monthly frequency
- Estimate FX innovations factor: Use AR(1) for volatility level, residuals as proxy for innovations, or use monthly change in FX volatility
- Sort currencies into 5 portfolios based on past beta with innovations to global FX volatility
- Use 36-month rolling window for beta estimates
- Go long on low volatility beta currencies (high volatility risk), short on high volatility beta currencies (low volatility risk)
- Equally weighted portfolio, rebalanced every 6 months

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1983-2009
- **Annual Return:** 4.2%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.48
- **Annual Standard Deviation:** 8.68%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
import statsmodels.api as sm

class FXVolatilityStrategy(bt.Strategy):
    params = (
        ('rebalance_months', 6),
        ('lookback_period', 36),
    )

    def __init__(self):
        self.months_passed = 0

    def next(self):
        if len(self.data) < self.params.lookback_period:
            return

        if self.months_passed % self.params.rebalance_months == 0:
            self.rebalance_portfolio()

        self.months_passed += 1

    def rebalance_portfolio(self):
        currencies_data = self.get_currencies_data()
        betas = self.calculate_betas(currencies_data)
        longs, shorts = self.get_long_short_positions(betas)

        for i, d in enumerate(self.datas):
            if d._name in longs:
                self.order_target_percent(d, target=1 / len(longs))
            elif d._name in shorts:
                self.order_target_percent(d, target=-1 / len(shorts))
            else:
                self.order_target_percent(d, target=0)

    def get_currencies_data(self):
        currencies_data = {}

        for d in self.datas:
            currency_data = pd.Series(d.close.get(size=self.params.lookback_period))
            currencies_data[d._name] = currency_data.pct_change().apply(np.log).abs().resample('M').mean()

        return currencies_data

    def calculate_betas(self, currencies_data):
        betas = {}

        for currency, data in currencies_data.items():
            x = sm.add_constant(data.shift(1).dropna())
            y = data.diff().dropna()
            model = sm.OLS(y, x).fit()
            betas[currency] = model.params[1]

        return betas

    def get_long_short_positions(self, betas):
        sorted_betas = sorted(betas.items(), key=lambda x: x[1])
        n = len(sorted_betas) // 5
        longs = [x[0] for x in sorted_betas[:n]]
        shorts = [x[0] for x in sorted_betas[-n:]]

        return longs, shorts

```