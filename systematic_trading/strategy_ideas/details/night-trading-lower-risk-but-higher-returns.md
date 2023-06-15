<div align="center">
  <h1>Night Trading: Lower Risk But Higher Returns?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2633476)

## Trading rules

- Investment universe: NYSE/AMEX/Nasdaq stocks
- Annual stock selection: Choose stocks with high potential for overnight returns
    - Simple approach: Sort stocks by previous year’s nightly performance and pick top decile
    - Regression model: Use equation 8 on page 19 to sort stocks into 4 groups based on susceptibility to elevated/depressed overnight returns
- Daily trading:
    - Buy stocks in the significant night performer group at market close
    - Short stocks in the significant night laggard group at market close
    - Hold long-short portfolio overnight and liquidate at market open
- Stock weighting: Equal weight for each stock

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1995-2014
- **Annual Return:** 21.28%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.62
- **Annual Standard Deviation:** 6.6%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression

class OvernightMomentum(bt.Strategy):
    params = (
        ('selection_method', 'simple'),
    )

    def __init__(self):
        self.daily_close = {}
        self.daily_open = {}
        self.stock_weights = {}
        self.selected_stocks = set()

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            self.select_stocks()

        for data in self.datas:
            if data._name in self.selected_stocks:
                if self.daily_close[data._name] < data.close[0]:
                    self.buy(data=data, exectype=bt.Order.Close)
                elif self.daily_close[data._name] > data.close[0]:
                    self.sell(data=data, exectype=bt.Order.Close)

            self.daily_close[data._name] = data.close[0]
            self.daily_open[data._name] = data.open[0]

    def select_stocks(self):
        stock_returns = {}
        for data in self.datas:
            stock_returns[data._name] = self.calculate_stock_returns(data)

        if self.params.selection_method == 'simple':
            sorted_stocks = sorted(stock_returns.items(), key=lambda x: x[1], reverse=True)
            self.selected_stocks = set([stock[0] for stock in sorted_stocks[:int(len(sorted_stocks) * 0.1)]])

        elif self.params.selection_method == 'regression':
            overnight_returns = np.array(list(stock_returns.values())).reshape(-1, 1)
            daily_total_returns = np.array([self.daily_close[name] / self.daily_open[name] for name in stock_returns.keys()]).reshape(-1, 1)
            model = LinearRegression()
            model.fit(daily_total_returns, overnight_returns)
            predictions = model.predict(daily_total_returns)
            sorted_indices = np.argsort(predictions, axis=0)[::-1].flatten()
            top_quartile = sorted_indices[:int(len(sorted_indices) * 0.25)]
            bottom_quartile = sorted_indices[-int(len(sorted_indices) * 0.25):]
            self.selected_stocks = set([list(stock_returns.keys())[i] for i in np.concatenate((top_quartile, bottom_quartile))])

    def calculate_stock_returns(self, data):
        return np.prod(data.close.get(ago=-1, size=252) / data.open.get(ago=-1, size=252)) - 1
```

This Python code is a Backtrader strategy for the “Overnight Momentum” trading strategy. Please note that this is only the strategy code and does not include data fetching, preprocessing, or the full Backtrader setup. Additionally, it assumes that the input data has been adjusted for splits and dividends.