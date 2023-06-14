<div align="center">
  <h1>Modeling, Forecasting and Trading the Crude Oil Term Structure.</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2874869)

## Trading rules

- Investment universe consists of WTI futures.
- Calculate Dynamic Nelson-Siegel (N-S) model to forecast the term structure for 30,60,…,360 days.
- Forecast the Beta parameters using AR-1 model with coefficients of level, slope and curvature.
- Use a sliding window of the last 156 weeks to estimate parameters with LAD Lasso.
- Calculate NS-term-structure at each Wednesday and forecast term structure for the next Wednesday.
- Select fixed futures pair: 2nd and 12th.
- Calculate weekly return due to term structure movement and futures’ movement down the term structure for each future.
- Long the future with higher weekly return and short the other one.
- Repeat the procedure next Wednesday.
- If the 2nd and 12th future hasn’t changed and long-short relationship is the same, trade one-week further.
- Close or reverse the position if the term-structure has turned around and it is profitable to do so.
- Decision to close or turn around is based on estimated return.
- If return is less than 0.3%, close the position.
- If larger return is forecasted, turn around the position.

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 2011-2016
- **Annual Return:** 5.4%
- **Maximum Drawdown:** -6.94%
- **Sharpe Ratio:** 0.76
- **Annual Standard Deviation:** 7.1%

## Python code

### Backtrader

```python
import backtrader as bt

# Define WTI futures
class WtiFutures(bt.Strategy):
    params = (
        ('tf_2nd', 2),
        ('tf_12th', 12),
        ('lad_lasso_lookback', 156),
    )

    def __init__(self):
        # Load the WTI futures data
        self.data = self.datas[0]

        # Initialize Dynamic Nelson-Siegel (N-S) model to forecast the term structure
        self.ns = bt.talib.DEMA(self.data.close, timeperiod=30)

        # Initialize AR-1 model to forecast the beta parameters
        self.ar1 = bt.ind.OLS_Transformation(self.ns, period=1)

        # Initialize LAD Lasso model to estimate the parameters with a sliding window
        self.lad_lasso = bt.talib.LASSO(self.data.close, lookback=self.params.lad_lasso_lookback)

        # Initialize the last Wednesday
        self.last_wednesday = None

        # Initialize the long and short futures contracts
        self.long_contract = None
        self.short_contract = None

        # Initialize the return
        self.last_return = None
        self.current_return = None

    def next(self):
        # Check if it is Wednesday
        if self.datetime.weekday() == bt.date.Wednesday:
            # Calculate the NS-term-structure
            ns_ts = self.ns[0:6]

            # Forecast the term structure for the next Wednesday
            next_ns_ts = self.ns[6:12]

            # Calculate the beta parameters using the AR-1 model
            beta = self.ar1.beta[0]

            # Estimate the parameters with LAD Lasso
            parameters = self.lad_lasso.params

            # Select the long and short futures contracts
            if ns_ts[self.params.tf_2nd] < ns_ts[self.params.tf_12th]:
                self.long_contract = self.datas[self.params.tf_2nd]
                self.short_contract = self.datas[self.params.tf_12th]
            else:
                self.long_contract = self.datas[self.params.tf_12th]
                self.short_contract = self.datas[self.params.tf_2nd]

            # Calculate the weekly return due to term structure movement and futures' movement down the term structure for each future
            self.last_return = self.current_return
            self.current_return = (next_ns_ts[self.params.tf_2nd] - ns_ts[self.params.tf_2nd]) - beta * (self.long_contract.close[0] - self.short_contract.close[0])

            # Long the future with higher weekly return and short the other one
            if self.current_return > 0:
                self.buy(self.long_contract)
                self.sell(self.short_contract)
            else:
                self.buy(self.short_contract)
                self.sell(self.long_contract)

            # Check if the position should be closed or turned around if the term-structure has turned around
            if self.last_wednesday:
                if next_ns_ts[self.params.tf_2nd] > self.last_wednesday[self.params.tf_2nd]:
                    if self.current_return < 0.003:
                        self.close()
                    elif self.current_return > self.last_return:
                        self.close()
                        self.buy(self.short_contract)
                        self.sell(self.long_contract)

            # Update the last Wednesday
            self.last_wednesday = next_ns_ts
```