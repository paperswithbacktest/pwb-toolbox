<div align="center">
  <h1>Earnings Management and the Post-Earnings Announcement Drift</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1010103)

## Trading rules

- Investment universe: All stocks from NYSE, AMEX, and NASDAQ
- Calculate abnormal accruals using the regression equation
- Estimate the accrual model four quarters prior to portfolio formation
- Apply the model’s parameters to individual firms in the portfolio formation quarter
- Define standardized earnings changes (SUE) as a seasonal change in net income to total assets ratio
- Sort stocks into quintiles based on SUE and abnormal accruals
- Go long on firms with:
    - Large positive earnings changes (top SUE quintile)
    - Large negative abnormal accruals (bottom quintile)
- Go short on firms with:
    - Large negative earnings changes (bottom SUE quintile)
    - Large positive abnormal accruals (top quintile)
- Hold long and short positions for six months from the 18th day after the earnings announcement

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1990-2006
- **Annual Return:** 42.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.49
- **Annual Standard Deviation:** 15.6%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class AccrualAnomalyStrategy(bt.Strategy):
    def __init__(self):
        self.quarters_passed = 0

    def next(self):
        if len(self.data) % 63 == 0:  # 63 trading days in a quarter
            self.quarters_passed += 1

        if self.quarters_passed >= 4:
            # Calculate SUE and abnormal accruals for all stocks
            stock_data = {}
            for d in self.datas:
                ticker = d.params.name
                df = pd.DataFrame({
                    'date': d.datetime.date(ago=0),
                    'net_income': d.net_income.array,
                    'total_assets': d.total_assets.array,
                    'cash_flow_operations': d.cash_flow_operations.array
                })
                df['total_accruals'] = df['net_income'] - df['cash_flow_operations']
                df['roa'] = df['net_income'] / df['total_assets']
                df['seasonal_roa'] = df['roa'] - df['roa'].shift(4)
                df['sue'] = df['seasonal_roa'] / df['seasonal_roa'].std()

                # Perform linear regression to estimate abnormal accruals
                X = df[['total_accruals', 'total_assets']].shift(4).dropna()
                y = df['total_accruals'][4:]
                model = LinearRegression().fit(X, y)
                df['abnormal_accruals'] = y - model.predict(X)

                stock_data[ticker] = df.iloc[-1]

            # Sort stocks into quintiles based on SUE and abnormal accruals
            sorted_data = pd.DataFrame(stock_data).T
            sorted_data['sue_quintile'] = pd.qcut(sorted_data['sue'], 5, labels=False)
            sorted_data['accrual_quintile'] = pd.qcut(sorted_data['abnormal_accruals'], 5, labels=False)

            # Select long and short positions
            long_positions = sorted_data[(sorted_data['sue_quintile'] == 4) & (sorted_data['accrual_quintile'] == 0)].index
            short_positions = sorted_data[(sorted_data['sue_quintile'] == 0) & (sorted_data['accrual_quintile'] == 4)].index

            # Execute trades
            for d in self.datas:
                ticker = d.params.name
                if ticker in long_positions and self.getposition(d).size == 0:
                    self.buy(data=d)
                elif ticker in short_positions and self.getposition(d).size == 0:
                    self.sell(data=d)
                elif self.getposition(d).size != 0 and self.getposition(d).days_in_trade >= 126:
                    self.close(data=d)

cerebro = bt.Cerebro()

# Add data feeds to cerebro with appropriate fields (net_income, total_assets, cash_flow_operations)
# ...

cerebro.addstrategy(AccrualAnomalyStrategy)
cerebro.run()
```

Please note that this code assumes that you have added data feeds to `cerebro` with the appropriate fields (`net_income`, `total_assets`, and `cash_flow_operations`). You will need to load the data for all stocks from NYSE, AMEX, and NASDAQ and add those data feeds with the required fields to `cerebro`.