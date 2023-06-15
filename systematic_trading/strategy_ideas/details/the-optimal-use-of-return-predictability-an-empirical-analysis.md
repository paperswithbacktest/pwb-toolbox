<div align="center">
  <h1>The Optimal Use of Return Predictability: An Empirical Analysis</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=677009)

## Trading rules

S&P 500 Market Timing: Harnessing VIX & COT Report Data

- Define open interest as total outstanding futures contracts not yet closed by offsetting transactions
- Equate aggregate long open interest to aggregate short open interest
- Calculate hedging pressure as the ratio of total commercial long positions to the sum of commercial long and short positions
- Employ linear regression to forecast excess market return (market return minus risk-free return) using VIX volatility, hedging pressure, and open interest as independent variables
- Utilize excess market return for S&P index and S&P volatility as inputs for optimization calculations to determine optimal weights of equities and risk-free assets for the upcoming period
- Seek a minimum variance portfolio through optimization, either analytically or numerically
- Apply the calculated weights for the immediate trading period
- Conduct regression and optimization calculations monthly and rebalance the portfolio accordingly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 2000-2005
- **Annual Return:** 9.7%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.52
- **Annual Standard Deviation:** 11%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression

class SP500MarketTiming(bt.Strategy):
    params = (
        ('risk_free_rate', 0.03),
        ('rebalance_period', 30)
    )

    def __init__(self):
        self.vix = bt.feeds.VIXData(dataname='vix.csv')
        self.cot_report = bt.feeds.COTReportData(dataname='cot_report.csv')
        self.days_passed = 0

    def next(self):
        if self.days_passed % self.params.rebalance_period == 0:
            open_interest = self.cot_report.total_open_interest[0]
            commercial_long = self.cot_report.commercial_long[0]
            commercial_short = self.cot_report.commercial_short[0]
            hedging_pressure = commercial_long / (commercial_long + commercial_short)
            X = np.column_stack((self.vix[0], hedging_pressure, open_interest))
            y = self.data.close[0] - self.params.risk_free_rate
            regression_model = LinearRegression().fit(X, y)
            excess_market_return = regression_model.predict(X)

            def objective_function(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

            constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
            bounds = [(0, 1), (0, 1)]
            initial_guess = [0.5, 0.5]
            optimal_weights = minimize(objective_function, initial_guess, bounds=bounds, constraints=constraints)

            self.order_target_percent(self.data, optimal_weights.x[0])
            self.order_target_percent(self.vix, optimal_weights.x[1])

        self.days_passed += 1

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SP500MarketTiming)
    data = bt.feeds.YahooFinanceData(dataname='^GSPC', fromdate='2000-01-01', todate='2005-12-31')
    cerebro.adddata(data)
    cerebro.run()
    cerebro.plot()
```

Please note that you will need to prepare the VIX and COT report data feeds (vix.csv and cot_report.csv) before running this script. The code above assumes that these data feeds are in CSV format with the necessary fields.