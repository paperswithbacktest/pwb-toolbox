<div align="center">
  <h1>The Unintended Impact of Academic Research on Asset Returns: The CAPM Alpha</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3054718)

## Trading rules

- Investment universe: Common stocks on NYSE, NASDAQ, AMEX (excluding REITs and ADRs)
- Create 3 data sets using NYSE breakpoints:
    - Small: Market cap ≤ 30th percentile
    - Medium: 30th percentile < Market cap ≤ 70th percentile
    - Big: Market cap > 70th percentile
- Focus on the Big data set
- Estimate betas and alphas with OLS regressions using CAPM model (past 5 years data)
- Determine median alpha
- Sell portfolio: Assets with realized alpha > median alpha
- Long portfolio: Assets with realized alpha < median alpha
- Rebalance portfolio yearly
- Asset i’s alpha i: Correlation coefficient between asset i returns and Market returns × (estimated asset i volatility / estimated Market volatility)
- Final market alpha for asset i: Alpha i × 0.6 + 0.4
- Low alpha portfolio:
    - Number of assets: nl
    - Vector of alpha ranks: zl
    - Asset i weight: (nl - zl for i + 1) / sum(zl for every i)
- High alpha portfolio:
    - Number of assets: nh
    - Vector of alpha ranks: zh
    - Asset i weight: (zh for every i) / sum(zh i for every i)
- Sum of weights for both portfolios: 1
- Final weighted market alpha:
    - Low alpha portfolio: α_low = sum(wl i × market alpha i for every i)
    - High alpha portfolio: α_high = sum(wh i × market alpha i for every i)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1973-2017
- **Annual Return:** 10.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.31
- **Annual Standard Deviation:** 20.29%

## Python code

### Backtrader

Here is the Backtrader Python code for the trading strategy:

```python
import backtrader as bt
import numpy as np
import pandas as pd
import statsmodels.api as sm

class BigStocksAlpha(bt.Strategy):
    def __init__(self):
        self.rebalance_days = 0

    def next(self):
        if self.rebalance_days > 0:
            self.rebalance_days -= 1
            return

        if len(self.datas[0]) < 5 * 252:
            return

        alphas, betas, market_caps = [], [], []

        for data in self.datas:
            returns = pd.Series(data.get(size=5 * 252)).pct_change().dropna()
            market_returns = returns.iloc[:, 0]
            asset_returns = returns.iloc[:, 1]
            X = sm.add_constant(market_returns)
            Y = asset_returns
            model = sm.OLS(Y, X).fit()
            alpha, beta = model.params[0], model.params[1]
            market_cap = data.market_cap[0]
            alphas.append(alpha)
            betas.append(beta)
            market_caps.append(market_cap)

        alphas = np.array(alphas)
        betas = np.array(betas)
        market_caps = np.array(market_caps)

        big_stocks = market_caps > np.percentile(market_caps, 70)
        alphas_big = alphas[big_stocks]
        median_alpha = np.median(alphas_big)
        long_stocks = alphas_big < median_alpha
        short_stocks = alphas_big > median_alpha

        self.rebalance_days = 252
        self.order_target_percent(self.data0, 0.0)

        for data, alpha in zip(self.datas[big_stocks][long_stocks], alphas_big[long_stocks]):
            weight = (1 - np.argsort(np.argsort(alphas_big[long_stocks])) + 1) / np.sum(np.argsort(np.argsort(alphas_big[long_stocks])) + 1)
            self.order_target_percent(data, weight)

        for data, alpha in zip(self.datas[big_stocks][short_stocks], alphas_big[short_stocks]):
            weight = (np.argsort(np.argsort(alphas_big[short_stocks])) + 1) / np.sum(np.argsort(np.argsort(alphas_big[short_stocks])) + 1)
            self.order_target_percent(data, -weight)
```

Please note that you need to add your own data feeds to the ‘cerebro’ instance. Also, this code assumes that each data feed has a ‘market_cap’ line that provides the market capitalization for each stock.