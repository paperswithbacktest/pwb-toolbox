<div align="center">
  <h1>International Volatility Arbitrage</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3203445)

## Trading rules

- Identify international option products (refer to table A.1 in the paper for a complete list)
- Calculate implied volatility returns: 1 - (previous year realized volatility / time t implied volatility)
    - Realized volatility: derived from daily data of underlying returns over the last 12 months
    - Time t implied volatility: average of ATM call and ATM put options at time t
- Sort ATM straddles in descending order based on previous day volatility returns
- Divide sorted straddles into three equally weighted tercile portfolios
- Construct long-short portfolio: sell expensive tercile (high) and buy cheap tercile (low)
- Execute trades on the fourth Friday of each month

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2006-2015
- **Annual Return:** 16.38%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.83
- **Annual Standard Deviation:** 8.93%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class InternationalVolatilityArbitrage(bt.Strategy):
    def __init__(self):
        self.options = self._identify_international_option_products()
        self.atm_straddles = []

    def _identify_international_option_products(self):
        # Implement the logic to identify international option products
        # Please refer to table A.1 in the paper for a complete list
        pass

    def _calculate_implied_volatility_returns(self, data):
        prev_year_realized_vol = data['underlying_returns'].rolling(window=252).std().shift(1)
        time_t_implied_vol = (data['atm_call'] + data['atm_put']) / 2
        return 1 - (prev_year_realized_vol / time_t_implied_vol)

    def _sort_straddles(self):
        sorted_straddles = sorted(self.atm_straddles, key=lambda x: x['vol_ret'], reverse=True)
        return sorted_straddles

    def _tercile_portfolios(self, sorted_straddles):
        tercile_size = len(sorted_straddles) // 3
        return np.array_split(sorted_straddles, [tercile_size, tercile_size * 2])

    def next(self):
        for d in self.datas:
            self.atm_straddles.append({
                'data': d,
                'vol_ret': self._calculate_implied_volatility_returns(d)
            })

        sorted_straddles = self._sort_straddles()
        tercile_portfolios = self._tercile_portfolios(sorted_straddles)

        # Check if it's the fourth Friday of the month
        if bt.TimeFrame.Ticks[self.data._timeframe] == bt.TimeFrame.Ticks.Month and self.data.datetime.weekday() == 4:
            # Sell expensive tercile (high)
            for data in tercile_portfolios[0]:
                self.sell(data['data'])

            # Buy cheap tercile (low)
            for data in tercile_portfolios[2]:
                self.buy(data['data'])

        # Clear the atm_straddles list for the next iteration
        self.atm_straddles = []

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(InternationalVolatilityArbitrage)

    # Add data feeds here
    # Implement the logic to load and add data feeds for options and underlying assets

    cerebro.run()
```

Please note that this code is just a starting point and does not include the actual options data or table A.1 from the paper. You’ll need to provide the appropriate options data and implement the `_identify_international_option_products()` method to get the complete list of international option products.