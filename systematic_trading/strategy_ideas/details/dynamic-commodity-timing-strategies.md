<div align="center">
  <h1>Dynamic Commodity Timing Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=581423)

## Trading rules

- Use GSCI index (or GSG ETF) for trading
- Employ three periods: estimation in-sample, training, and trading
- Utilize 15 forecasting variables in the in-sample period
- Restrict explanatory variables to between 0 and 5 (4,944 possible models)
- Estimate parameters using OLS regression
- Generate monthly signals during a 24-month training period
- Buy GSCI-index futures for positive signals, sell for negative signals
- Rank models based on realized information ratios and transaction costs
- Select model with highest realized information ratio for next month’s forecast
- Use a 60-month in-sample estimation window, 24-month training period, and 1-month trading period
- Dynamically re-estimate and re-select models monthly
- Rebalance strategy on a monthly basis

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1992-2003
- **Annual Return:** 11.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.43
- **Annual Standard Deviation:** 18%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
import statsmodels.api as sm
from itertools import combinations

class GSCIIndexStrategy(bt.Strategy):
    params = (
        ("insample_window", 60),
        ("training_period", 24),
        ("trading_period", 1),
        ("num_variables", 15),
        ("min_variables", 0),
        ("max_variables", 5),
    )

    def __init__(self):
        self.month_counter = 0
        self.best_model = None

    def next(self):
        self.month_counter += 1
        if self.month_counter % self.params.trading_period == 0:
            self.rebalance()

    def rebalance(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            insample_data = self.data.get(size=self.params.insample_window)
            self.best_model = self.select_best_model(insample_data)
            training_data = self.data.get(size=self.params.training_period)
            signal = self.generate_signal(self.best_model, training_data)
            if signal > 0:
                self.buy()
            elif signal < 0:
                self.sell()

    def select_best_model(self, data):
        best_ir = -np.inf
        best_model = None
        for num_vars in range(self.params.min_variables, self.params.max_variables + 1):
            for combo in combinations(range(self.params.num_variables), num_vars):
                X = data[:, combo]
                X = sm.add_constant(X)
                y = data[:, -1]
                model = sm.OLS(y, X).fit()
                ir = model.tvalues[-1] / model.bse[-1]
                if ir > best_ir:
                    best_ir = ir
                    best_model = model
        return best_model

    def generate_signal(self, model, data):
        X = data[:, model.params.index[1:]]
        X = sm.add_constant(X)
        signal = model.predict(X[-1])
        return signal

if __name__ == "__main__":
    cerebro = bt.Cerebro()
    cerebro.addstrategy(GSCIIndexStrategy)
    data = bt.feeds.YahooFinanceData(dataname="GSG", fromdate="1990-01-01", todate="2021-09-30")
    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.002)
    print("Starting Portfolio Value:", cerebro.broker.getvalue())
    cerebro.run()
    print("Final Portfolio Value:", cerebro.broker.getvalue())
```

Please note that this code is a simplified version of the strategy, and you may need to adjust or add features depending on your specific data and requirements. You will also need to provide the appropriate data containing the forecasting variables for the strategy to work correctly.