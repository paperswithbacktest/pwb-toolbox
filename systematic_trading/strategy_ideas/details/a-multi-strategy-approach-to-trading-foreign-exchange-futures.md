<div align="center">
  <h1>A Multi Strategy Approach to Trading Foreign Exchange Futures</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3322717)

## Trading rules

- Investment Universe: 8 most liquid current month FX futures on CME for AUD, GBP, CAD, EUR, JPY, MXN, NZD, and CHF
- Individual Strategies (Indicators):
    - Interest Rate Carry
    - Momentum
    - Mean Reversion
    - Equity Momentum
    - Commodity Momentum
- Indicator Normalization:
    - Calculate percentile score (range 0-1)
    - Subtract 0.5 to remove long bias
- Risk Budgeting:
    - Proportional to absolute value of normalized indicator values
    - 10% annualized total risk
    - Constant risk target across indicators
    - Modified optimization for negative weights
- Strategy Combination:
    - Equal weighting
    - Monthly rebalancing

## Statistics

- **Markets Traded:** currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1995-2019
- **Annual Return:** 6.58%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.5
- **Annual Standard Deviation:** 13.16%

## Python code

### Backtrader

Here is the Backtrader python code for the given trading rules:

```python
import backtrader as bt
import math
import pandas as pd
import numpy as np
from scipy import stats

class ForexStrategy(bt.Strategy):
    params = ( ('carry_period', 30), ('momentum_period', 30), ('mean_reversion_period', 30), ('equity_momentum_period', 30), ('commodity_momentum_period', 30), ('rebalance_period', 30), ('annualized_risk', 0.1), )

    def __init__(self):
        self.current_month_fx_futures = [
            'AUD', 'GBP', 'CAD', 'EUR', 'JPY', 'MXN', 'NZD', 'CHF']

        self.indicators = {
            'interest_rate_carry': {},
            'momentum': {},
            'mean_reversion': {},
            'equity_momentum': {},
            'commodity_momentum': {}
        }

        for currency in self.current_month_fx_futures:
            self.indicators['interest_rate_carry'][currency] = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.params.carry_period)
            self.indicators['momentum'][currency] = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.params.momentum_period)
            self.indicators['mean_reversion'][currency] = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.params.mean_reversion_period)
            self.indicators['equity_momentum'][currency] = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.params.equity_momentum_period)
            self.indicators['commodity_momentum'][currency] = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.params.commodity_momentum_period)

    def next(self):
        if self.datas[0].datetime.date(ago=0) % self.params.rebalance_period == 0:
            for currency in self.current_month_fx_futures:
                carry = self.indicators['interest_rate_carry'][currency][0]
                momentum = self.indicators['momentum'][currency][0]
                mean_reversion = self.indicators['mean_reversion'][currency][0]
                equity_momentum = self.indicators['equity_momentum'][currency][0]
                commodity_momentum = self.indicators['commodity_momentum'][currency][0]

                indicator_values = [carry, momentum, mean_reversion,
                                    equity_momentum, commodity_momentum]

                # Normalize indicator values
                percentile_scores = [stats.percentileofscore(indicator_values, val) / 100
                                    for val in indicator_values]
                normalized_values = [score - 0.5 for score in percentile_scores]

                # Risk budgeting
                risk_budget = [abs(val) for val in normalized_values]
                target_risk = self.params.annualized_risk / math.sqrt(12)
                weight = [target_risk * (val / sum(risk_budget)) for val in risk_budget]

                # Equal weighting and monthly rebalancing
                position_size = self.broker.getvalue() * (1/len(self.current_month_fx_futures))
                for i, d in enumerate(self.datas):
                    self.order_target_value(d, position_size * weight[i])

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    data = bt.feeds.GenericCSVData(
        dataname='your-data-file.csv',
        datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1)
    cerebro.run()
```
