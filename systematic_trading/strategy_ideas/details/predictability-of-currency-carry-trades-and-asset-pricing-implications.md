<div align="center">
  <h1>Predictability of Currency Carry Trades and Asset Pricing Implications</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1977642)

## Trading rules

- The investment universe consists of 8 currencies: Australian Dollar, Canadian Dollar, Swiss Franc, British Pound, Japanese Yen, Norwegian Krone, New Zealand Dollar, and Swedish Krona.
- Currencies are sorted based on their interest rate differentials against the US dollar as inferred through the forward discounts.
- A basic carry trade strategy buys the highest-yielding currency and sells the lowest-yielding counterpart.
- Three prediction variables are used to time a basic carry trade strategy:
    - Three-month log change in the Raw Industrials sub-index of the CRB Spot Commodity Index
    - Normalized daily log changes in average currency volatility
    - Aggregate liquidity variable calculated as an average of the equivalents of the TED spread across the currencies used in this sample
- A linear regression is used to forecast the future one-month carry trade return with 3 independent prediction variables.
- The predictive regression model is estimated with an expanding window, taking an initial length of 180 months.
- The investor adopts a decision rule to take a position in a carry trade (based on the rank-ordering of forward discounts at the end of month t) if the predictive regression model predicts a positive carry trade payoff for month t+1.
- If the model predicts a negative payoff, the investor refrains from entering into a carry trade.

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1985-2011
- **Annual Return:** 12.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.86
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
# Importing Libraries
import pandas as pd
import numpy as np
import statsmodels.api as sm
import backtrader as bt

# Creating a Strategy class
class CarryTrade(bt.Strategy):

    def __init__(self):
        # Setting Universe
        self.assets = ['AUDUSD', 'CADUSD', 'CHFUSD', 'GBPUSD', 'JPYUSD', 'NOKUSD', 'NZDUSD', 'SEKUSD']
        # Setting Predictors
        self.ri = self.datas[0].raw_industrial
        self.cov = self.datas[0].average_currency_volatility
        self.liquidity = self.datas[0].aggregate_liquidity
        # Setting Counter for Live Trading
        self.counter = 0

        # Setting Initial Variables
        self.window = 180
        self.index = self.window
        self.invested = False

    def next(self):
        # Going Through Window Period for Linear Regression
        if self.index > self.window:
            # Creating DataFrame with Predictors
            data = pd.DataFrame({
                'ri': [np.log(self.ri[i]*1.0/self.ri[i-63]) for i in range(self.index-63, self.index)],
                'cov': [(np.log(self.cov[i-1]) - np.log(self.cov[i-2]))/np.log(self.cov[i-2]) for i in range(self.index-62, self.index)]
            })
            data['liq'] = [(self.liquidity[i-1] + self.liquidity[i-2])/2 for i in range(self.index-62, self.index)]
            data = data.dropna()
            endog = np.array(data.loc[:, 'ri'])
            exog = np.array(data.loc[:, ['cov', 'liq']])
            exog = sm.add_constant(exog)

            # Running Linear Regression
            model = sm.OLS(endog, exog).fit()

            # Predicting Next Month's Returns
            pred_data = pd.DataFrame({
                'ri': [np.log(self.ri[self.index + i]*1.0/self.ri[self.index + i - 63]) for i in range(21, 63)],
                'cov': [(np.log(self.cov[self.index + i - 1]) - np.log(self.cov[self.index + i - 2]))/np.log(self.cov[self.index + i - 2]) for i in range(22, 63)],
            })
            pred_data['liq'] = [(self.liquidity[self.index + i - 1] + self.liquidity[self.index + i - 2])/2 for i in range(22, 63)]
            pred_data = pred_data.dropna()
            pred_exog = np.array(pred_data.loc[:, ['cov', 'liq']])
            pred_exog = sm.add_constant(pred_exog)
            pred_ret = model.predict(pred_exog)[-1]

            # Trading Rule
            if pred_ret > 0 and not self.invested:
                # Enter Long Position
                for i, asset in enumerate(self.assets):
                    if i == 0:
                        lot_size = (self.broker.get_cash() / self.datas[i].close[0]) * 0.5
                    else:
                        base = self.datas[i-1].close[0] * (1 if i == 1 or i == 4 else -1)
                        lot_size = (self.broker.get_value() * 0.02 * base) / self.datas[i].close[0]
                    self.buy(self.datas[i], size=lot_size)
                self.invested = True
            elif pred_ret <= 0 and self.invested:
                # Exit Position
                for i, asset in enumerate(self.assets):
                    self.sell(self.datas[i], size=self.getposition(self.datas[i]).size)
                self.invested = False
            self.counter += 1
        else:
            self.index += 1
```