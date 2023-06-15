<div align="center">
  <h1>The Price of Commodity Risk in Stock and Futures Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1785728)

## Trading rules

- Select top 20% largest market-cap stocks from NYSE, AMEX, and NASDAQ
- Create OIW commodity index using 33 liquid commodities, weighted by Total Open Interest (TOI)
- Estimate commodity betas for stocks in investment universe over a 60-month rolling window using regression
- Go long on top 20% stocks with highest commodity beta
- Go short on bottom 20% stocks with lowest commodity beta
- Use a value-weighted portfolio
- Rebalance monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2004-2010
- **Annual Return:** 12.49%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.51
- **Annual Standard Deviation:** 16.5%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class CommodityRiskFactorStrategy(bt.Strategy):
    def __init__(self):
        self.rebalance_days = 0
        self.rolling_window = 60
        self.top_pct = 0.2

    def next(self):
        if self.rebalance_days > 0:
            self.rebalance_days -= 1
            return

        market_caps = pd.Series({data: data.market_cap[0] for data in self.datas})
        largest_stocks = market_caps.nlargest(int(len(self.datas) * self.top_pct))
        betas = self.calculate_betas(largest_stocks.index)
        sorted_betas = betas.sort_values()
        long_stocks = sorted_betas.tail(int(len(sorted_betas) * self.top_pct)).index
        short_stocks = sorted_betas.head(int(len(sorted_betas) * self.top_pct)).index
        long_weights = largest_stocks.loc[long_stocks] / largest_stocks.loc[long_stocks].sum()
        short_weights = largest_stocks.loc[short_stocks] / largest_stocks.loc[short_stocks].sum()

        for data in self.datas:
            if data in long_stocks:
                self.order_target_percent(data, target=long_weights.loc[data])
            elif data in short_stocks:
                self.order_target_percent(data, target=-short_weights.loc[data])
            else:
                self.order_target_percent(data, target=0)

        self.rebalance_days = 30

    def calculate_betas(self, stocks):
        betas = pd.Series(index=stocks)
        oiw_index_returns = self.calculate_oiw_index_returns()

        for data in stocks:
            stock_returns = pd.Series(data.close.get(size=self.rolling_window)).pct_change().dropna()
            model = LinearRegression().fit(stock_returns.values.reshape(-1, 1), oiw_index_returns)
            betas[data] = model.coef_[0]

        return betas

    def calculate_oiw_index_returns(self):
        # Placeholder function, replace with actual logic to compute OIW index returns
        return pd.Series(np.random.random(self.rolling_window - 1))

cerebro = bt.Cerebro()
# Add data feeds to cerebro, assuming they have an extra line "market_cap"
# ...

cerebro.addstrategy(CommodityRiskFactorStrategy)
cerebro.run()
```

Please note that this code serves as a starting point and may require adjustments depending on your data source and the actual implementation of the OIW commodity index.