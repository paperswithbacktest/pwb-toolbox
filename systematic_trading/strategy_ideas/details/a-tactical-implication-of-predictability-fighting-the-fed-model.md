<div align="center">
  <h1>A Tactical Implication of Predictability: Fighting the Fed Model</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=517322)

## Trading rules

- Conduct a one-month predictive regression each month using available data to predict excess stock market returns with the yield gap as an independent variable
- Calculate the yield gap (YG) using the formula: YG = EY - y
    - Earnings yield (EY) = ln(1 + E/P)
    - Log 10-year Treasury bond yield (y) = ln(1 + Y)
- Allocate 100% to the risky asset if forecasted excess returns are positive
- Invest 100% in the risk-free rate if forecasted excess returns are negative

## Statistics

- **Markets Traded:** Bonds, equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1959-2003
- **Annual Return:** 11%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.7
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression

class FedModel(bt.Strategy):
    def __init__(self):
        self.yield_gap = None

    def next(self):
        data_len = len(self.data)
        if data_len < 30:
            return

        # Calculate Earnings Yield (EY)
        E = self.data.close[0]
        P = self.data.close[-1]
        EY = np.log(1 + E / P)

        # Calculate Log 10-year Treasury bond yield (y)
        Y = self.data.bond_yield[0]
        y = np.log(1 + Y)

        # Calculate Yield Gap (YG)
        self.yield_gap = EY - y

        # Conduct one-month predictive regression
        X = self.yield_gap[:-1].reshape(-1, 1)
        y = self.data.close[1:] - self.data.close[:-1]
        model = LinearRegression()
        model.fit(X, y)
        forecast = model.predict(self.yield_gap[-1].reshape(-1, 1))

        # Allocate 100% to risky asset if forecasted excess returns are positive
        if forecast > 0:
            self.order_target_percent(self.data, target=1.0)
        else:
            self.order_target_percent(self.data, target=0.0)


class FedModelData(bt.feeds.GenericCSVData):
    lines = ('bond_yield', )
    params = (('bond_yield', -1), )

cerebro = bt.Cerebro()
cerebro.addstrategy(FedModel)
data = FedModelData(dataname='path/to/your/csv/data')
cerebro.adddata(data)
cerebro.broker.setcash(100000.0)
cerebro.run()
```

Please note that you need to have a CSV data file with columns for the close prices and the 10-year Treasury bond yields. Replace `'path/to/your/csv/data'` with the actual path to your data file.