<div align="center">
  <h1>The Term Structure of Returns: Facts and Theory</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2597481)

## Trading rules

- Maintain continuous exposure to implied dividends by replicating a 1-year constant tenor dividend future through positions in dividend futures with expiry dates close to the desired 1-year tenor
- Roll positions daily, gradually reducing weight in the dividend future with the closest expiry to zero, while increasing the position in the other future to 100%
- Go long on “1-year constant maturity” dividend futures and hedge indirect equity exposure by shorting the SX5E index
- Calculate the hedge ratio daily using a linear regression of dividend futures returns versus SX5E returns from the previous two weeks

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 2008-2013
- **Annual Return:** 12.9%
- **Maximum Drawdown:** -28.8%
- **Sharpe Ratio:** 1.11
- **Annual Standard Deviation:** 11.6%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression

class DividendRiskPremiumStrategy(bt.Strategy):
    params = (
        ("lookback", 10),  # lookback period for linear regression (2 weeks)
    )

    def __init__(self):
        self.dividend_futures = self.datas[0]  # dividend futures data feed
        self.sx5e = self.datas[1]  # SX5E index data feed

    def next(self):
        div_returns = np.log(self.dividend_futures.close / self.dividend_futures.close(-1))
        sx5e_returns = np.log(self.sx5e.close / self.sx5e.close(-1))

        X = np.array(sx5e_returns.get(size=self.params.lookback)).reshape(-1, 1)
        y = np.array(div_returns.get(size=self.params.lookback)).reshape(-1, 1)
        model = LinearRegression().fit(X, y)
        hedge_ratio = model.coef_[0][0]

        self.order_target_percent(self.dividend_futures, target=1.0)
        self.order_target_percent(self.sx5e, target=-hedge_ratio)
```

Note that this code assumes you have already prepared data feeds that reflect the rolling process of dividend futures with expiry dates close to the desired 1-year tenor. Rolling the futures and managing the data feeds is outside the scope of this code snippet.