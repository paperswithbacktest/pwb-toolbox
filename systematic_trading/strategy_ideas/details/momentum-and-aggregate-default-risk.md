<div align="center">
  <h1>Momentum and Aggregate Default Risk</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2054707)

## Trading rules

- Investment universe: All AMEX/NYSE/NASDAQ stocks (excluding stocks below $1, foreign stocks, and ADRs)
- Stock sorting: Decile-based on cumulative performance over months t-6 through t-1, using Jegadeesh and Titman (1993) methodology
- Portfolio formation: Equally weighted firms in each decile, with top decile as winners and bottom decile as losers
- Momentum portfolios: Formed monthly and held for six months (6-1-6 basic momentum strategy)
- Aggregate default premium: Yield spread between Moody’s CCC corporate bond index and 10-year U.S. Treasury bond
- Unexpected default shocks: Derived as residuals from DEFt = a0 + a1*DEFt-1 + a2*DEFt-2 + XIt model
- Residual calculation: Begins with pre-sample period (Jan 1954 - Dec 1959), then iteratively adds one observation and re-estimates the model
- Default shock period determination: Monthly median value of aggregate default shocks used to categorize high or low default shock periods
- Portfolio holding: Momentum portfolio held only in high default shock periods

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1960-2009
- **Annual Return:** 25.78%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.98
- **Annual Standard Deviation:** 22.28%

## Python code

### Backtrader

import backtrader as bt import numpy as np import pandas as pd import statsmodels.api as sm

class MomentumStrategy(bt.Strategy):

```python
params = (
    ('lookback', 6),
    ('holding', 6),
    ('n_deciles', 10),
    ('min_price', 1.0),
)

def __init__(self):
    self.rankings = []

def next(self):
    # Rebalance only once per month
    if self.data.datetime.date(0).day != 1:
        return

    # Sort stocks into deciles based on past 6-month returns (excluding the last month)
    self.rankings = list(self.datas)
    self.rankings.sort(key=lambda d: d.close.get(size=self.p.lookback + 1)[0], reverse=True)

    # Define top and bottom deciles
    top_decile = self.rankings[:len(self.rankings) // self.p.n_deciles]
    bottom_decile = self.rankings[-len(self.rankings) // self.p.n_deciles:]

    # Calculate the default premium
    default_premium = moody_ccc_bond_index - ten_year_us_treasury_bond

    # Estimate unexpected default shocks using the DEFt model
    deft = pd.Series([default_premium[t - i] for i in range(3)])
    X = sm.add_constant(deft.shift(1).dropna())
    y = deft[1:]
    model = sm.OLS(y, X).fit()
    residuals = model.resid

    # Determine high default shock periods
    high_default_shock = residuals[-1] > residuals.median()

    # Hold momentum portfolio in high default shock periods only
    if high_default_shock:
        for d in top_decile:
            if self.getposition(d).size == 0 and d.close[0] > self.p.min_price:
                self.order_target_percent(d, target=1.0 / len(top_decile))

        for d in bottom_decile:
            self.order_target_percent(d, target=0)

    # Liquidate positions in low default shock periods
    else:
        for d in self.datas:
            self.order_target_percent(d, target=0)

    # Rebalance the portfolio
    self.rebalance_portfolio = False
    self.rebalance_on_bar += self.p.holding * 30  # Schedule the next rebalance in 6 months (approx. 30 trading days per month)
```