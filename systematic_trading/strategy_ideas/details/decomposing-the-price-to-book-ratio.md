<div align="center">
  <h1>Decomposing the Price-to-Book Ratio</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2679401)

## Trading rules

- Investment universe: 12,380 stocks listed on NYSE, AMEX, and NASDAQ (refer to Appendix B for inclusion criteria)
- Data source: Compustat database for accounting data
- Separate fundamental and transitory components of P/B ratio using regression analysis with firm-level accounting variables (current gross profit over asset, last year’s growth in gross profit, and a constant)
- Create two strategies: HMLFundamental and HMLTransitory
    - HMLFundamental: Sort stocks into quintiles based on fundamental component; go long on bottom quintile, short on top quintile
    - HMLTransitory: Follow the same process as HMLFundamental but based on transitory component
- In year t, go long on HMLTransitory strategy and short on HMLFundamental strategy using accounting data from t-1
- Rebalance portfolios annually
- Use value-weighted stocks in portfolios

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1981-2014
- **Annual Return:** 9.03%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.52
- **Annual Standard Deviation:** 9.71%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

class HMLFundamentalTransitory(bt.Strategy):
    def __init__(self):
        self.stocks = self.datas

    def prenext(self):
        self.next()

    def next(self):
        if self.strategy.datetime.month() != 12:
            return

        fundamental_components = []
        transitory_components = []

        for stock in self.stocks:
            accounting_data = self.get_accounting_data(stock)
            pb_ratio = accounting_data['pb_ratio']
            gross_profit_over_asset = accounting_data['gross_profit_over_asset']
            last_year_growth = accounting_data['last_year_growth']
            X = np.column_stack((gross_profit_over_asset, last_year_growth, np.ones_like(gross_profit_over_asset)))
            y = pb_ratio
            model = LinearRegression()
            model.fit(X, y)
            fitted_values = model.predict(X)
            residuals = y - fitted_values
            fundamental_components.append(fitted_values[-1])
            transitory_components.append(residuals[-1])

        quintile_size = len(self.stocks) // 5
        sorted_fundamental_indices = np.argsort(fundamental_components)
        sorted_transitory_indices = np.argsort(transitory_components)
        long_fundamental = sorted_fundamental_indices[:quintile_size]
        short_fundamental = sorted_fundamental_indices[-quintile_size:]
        long_transitory = sorted_transitory_indices[:quintile_size]
        short_transitory = sorted_transitory_indices[-quintile_size:]

        self.close_positions()

        for i in long_transitory:
            self.buy(data=self.stocks[i])

        for i in short_fundamental:
            self.sell(data=self.stocks[i])

    def close_positions(self):
        for stock in self.stocks:
            self.close(data=stock)

    def get_accounting_data(self, stock):
        # Implement function to fetch accounting data from Compustat database
        pass

cerebro = bt.Cerebro()

# Add stocks data from NYSE, AMEX, and NASDAQ to cerebro

cerebro.addstrategy(HMLFundamentalTransitory)
cerebro.run()
```

Please note that you will need to implement the `get_accounting_data` function to fetch accounting data from the Compustat database. Additionally, make sure to add stocks data from NYSE, AMEX, and NASDAQ to the `cerebro` object before running the strategy.