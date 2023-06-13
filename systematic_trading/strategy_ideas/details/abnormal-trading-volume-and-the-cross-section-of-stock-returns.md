<div align="center">
  <h1>Abnormal Trading Volume and the Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2812010)

## Trading rules

- Investment universe: Common stocks on NYSE, AMEX, NASDAQ
- Rolling-window regression: 36 months, formula on pg. 6 of paper
- Turnover components: ETURN (explained), UTURN (abnormal, unexplained)
- UTURN calculation: Residual divided by residual standard deviation
- Stock sorting: Quintiles based on UTURN
- Long position: Q5 quintile (lowest UTURN values)
- Short position: Q1 quintile (highest UTURN values)
- Portfolio weighting: Equally weighted
- Rebalancing: Monthly basis

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1968-2015
- **Annual Return:** 10.82%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.65
- **Annual Standard Deviation:** 10.45%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class UTurnStrategy(bt.Strategy):
    params = (
        ("lookback_period", 36),
        ("quintiles", 5),
    )

    def __init__(self):
        self.uturn = dict()

    def prenext(self):
        self.next()

    def next(self):
        if len(self.data) < self.params.lookback_period:
            return

        uturn_values = []
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            returns = pd.Series(data.close.get(size=self.params.lookback_period))
            explained_turnover = returns.shift(1)
            unexplained_turnover = returns - explained_turnover

            model = LinearRegression()
            model.fit(explained_turnover.values.reshape(-1, 1), unexplained_turnover.values)

            residual = unexplained_turnover - model.predict(explained_turnover.values.reshape(-1, 1))
            uturn = residual / residual.std()

            self.uturn[d] = uturn[-1]
            uturn_values.append(uturn[-1])

        sorted_symbols = sorted(self.uturn, key=self.uturn.get)
        quintile_size = int(len(sorted_symbols) / self.params.quintiles)

        long_symbols = sorted_symbols[-quintile_size:]
        short_symbols = sorted_symbols[:quintile_size]

        long_weight = 1.0 / len(long_symbols)
        short_weight = -1.0 / len(short_symbols)

        for d in self.getdatanames():
            data = self.getdatabyname(d)
            if d in long_symbols:
                self.order_target_percent(data, target=long_weight)
            elif d in short_symbols:
                self.order_target_percent(data, target=short_weight)
            else:
                self.order_target_percent(data, target=0.0)


if __name__ == "__main__":
    cerebro = bt.Cerebro()
    # Add data feeds for NYSE, AMEX, NASDAQ common stocks
    # (Replace "YOUR_DATA_FEEDS" with actual data feeds)
    for data_feed in YOUR_DATA_FEEDS:
        cerebro.adddata(data_feed)

    cerebro.addstrategy(UTurnStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

```

Replace “YOUR_DATA_FEEDS” with actual data feeds for common stocks on NYSE, AMEX, and NASDAQ. Note that the implementation provided assumes that the data feeds contain adjusted close prices.