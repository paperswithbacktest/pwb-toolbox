<div align="center">
  <h1>Firm Fundamental Cycle and Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3282420)

## Trading rules

- Investment universe: domestic common stocks listed on NYSE, AMEX, and Nasdaq stock markets
- Exclude: closed-end funds, REITs, unit trusts, ADRs, foreign stocks, and stocks priced below $1
- Use 13 firm fundamental ratios: profitability, financial leverage and strength, efficiency of asset management, and quality of earning and assets
- Calculate the average of each ratio for the same quarter over the past four years and subtract the average from the current quarter’s ratio (seasonally adjusted ratios)
- Calculate the change in seasonally adjusted ratios between two adjacent quarters for each stock
- Aggregate information using partial least square (PLS) approach for both level of seasonally adjusted ratios and unanticipated changes in them
- Forecast return in quarter t+1 using information up to quarter t by estimating regression parameters (a0, a1, a2) from equation 22 at page 29
- Calculate forecasted return using the average of estimated coefficients over past 10 quarters (for each stock)
- Sort stocks into decile portfolios based on forecasted returns
- Long the top decile, short the bottom decile
- Rebalance the strategy quarterly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1970-2015
- **Annual Return:** 8.8%
- **Maximum Drawdown:** -21.44%
- **Sharpe Ratio:** 0.7
- **Annual Standard Deviation:** 6.82%

## Python code

### Backtrader

Here is the python code for the Backtrader strategy, considering the given trading rules:

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression

class FundamentalMomentum(bt.Strategy):
    params = (('lookback', 10),)

    def __init__(self):
        self.data_open = self.datas[0].open
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume

    def next(self):
        if len(self.data_close) < self.p.lookback * 65:  # Roughly 4 years of data
            return

        if self.data_close.datetime.date(0).month % 3 == 0:  # Quarterly rebalancing
            data = self.get_fundamental_data()
            sorted_data = data.sort_values(by='forecasted_return')
            long_stocks = sorted_data.tail(10)  # Top decile
            short_stocks = sorted_data.head(10)  # Bottom decile

            # Long top decile stocks
            for stock in long_stocks.index:
                self.order_target_percent(stock, target=0.1)

            # Short bottom decile stocks
            for stock in short_stocks.index:
                self.order_target_percent(stock, target=-0.1)

    def get_fundamental_data(self):
        # Placeholder function to get fundamental data for each stock
        # This function should return a pandas DataFrame with stock symbols as index
        # and columns including seasonally adjusted ratios and changes in them
        pass

    def calculate_forecasted_return(self, data):
        past_quarters = 10
        pls = PLSRegression(n_components=2)
        forecasted_returns = []

        for stock in data.index:
            stock_data = data.loc[stock]
            X = stock_data[['seasonally_adjusted_ratios', 'unanticipated_changes']]
            y = stock_data['next_quarter_return']
            coef_sum = np.zeros(3)

            for i in range(-past_quarters, 0):
                X_train = X.iloc[i - past_quarters:i, :]
                y_train = y.iloc[i - past_quarters:i]
                pls.fit(X_train, y_train)
                coef_sum += pls.coef_

            avg_coef = coef_sum / past_quarters
            forecasted_return = np.dot(X.iloc[-1, :], avg_coef)
            forecasted_returns.append(forecasted_return)

        data['forecasted_return'] = forecasted_returns
        return data

class FundamentalMomentumStrategy(bt.Cerebro):
    def __init__(self):
        super().__init__()
        self.addstrategy(FundamentalMomentum)

    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)
```

Keep in mind that you need to implement the `get_fundamental_data()` function to obtain the required fundamental data and preprocess it according to the given rules. The code provided is just the basic structure for the Backtrader strategy.