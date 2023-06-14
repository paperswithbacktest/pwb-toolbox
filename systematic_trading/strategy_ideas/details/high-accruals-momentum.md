<div align="center">
  <h1>High Accruals Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3188172)

## Trading rules

- Define investment universe: NYSE, AMEX, NASDAQ common stocks (CRSP share codes 10 and 11)
- Estimate coefficients: Run regressions of total accruals on independent variables from Jones model (Equation 2, page 9) for each SIC code group and firm year
- Compute fitted and residual values: Non-discretionary and discretionary accruals, respectively
- Construct accruals momentum measure: Sort firms into yearly quartiles based on estimated discretionary accruals
- Identify low accruals momentum: Firms in lowest quartile for four consecutive years
- Identify high accruals momentum: Firms in highest quartile for four consecutive years
- Implement trading strategy: Long lowest momentum quartile, short highest momentum quartile

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1980-2016
- **Annual Return:** 9.94%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.54
- **Annual Standard Deviation:** 11.1%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

class AccrualsMomentum(bt.Strategy):
    def __init__(self):
        self.stocks = self.datas

    def prenext(self):
        self.next()

    def next(self):
        end_of_year = self.datas[0].datetime.date(-1).year != self.datas[0].datetime.date().year
        if end_of_year:
            accruals_momentum = self.compute_accruals_momentum()
            low_momentum_stocks, high_momentum_stocks = self.identify_momentum_stocks(accruals_momentum)
            for stock in self.stocks:
                if stock in low_momentum_stocks:
                    self.order_target_percent(stock, target=1/len(low_momentum_stocks))
                elif stock in high_momentum_stocks:
                    self.order_target_percent(stock, target=-1/len(high_momentum_stocks))
                else:
                    self.order_target_percent(stock, target=0)

    def compute_accruals_momentum(self):
        momentum_scores = {}
        for stock in self.stocks:
            discretionary_accruals = self.compute_discretionary_accruals(stock)
            momentum_scores[stock] = discretionary_accruals
        return momentum_scores

    def compute_discretionary_accruals(self, stock):
        # Load financial statement data and run Jones Model regression here
        # Compute residuals (discretionary accruals)
        # This implementation assumes that you have already computed discretionary accruals
        return stock.discretionary_accruals

    def identify_momentum_stocks(self, accruals_momentum):
        sorted_stocks = sorted(self.stocks, key=lambda stock: accruals_momentum[stock])
        quartile_size = len(sorted_stocks) // 4
        low_momentum_stocks = sorted_stocks[:quartile_size]
        high_momentum_stocks = sorted_stocks[-quartile_size:]
        return low_momentum_stocks, high_momentum_stocks

if __name__ == "__main__":
    cerebro = bt.Cerebro()
    # Load investment universe (NYSE, AMEX, NASDAQ common stocks) data here
    # This implementation assumes that you have already prepared data with CRSP share codes 10 and 11
    cerebro.adddata(data)
    cerebro.addstrategy(AccrualsMomentum)
    cerebro.run()
```

Please note that this code assumes that you have already prepared the data with the CRSP share codes 10 and 11, and the financial statement data for the Jones Model regression. Make sure to adjust the code accordingly to match your data and handle any missing values.