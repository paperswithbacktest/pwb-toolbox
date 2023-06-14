<div align="center">
  <h1>Idiosyncratic Momentum in Commodity Futures</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3035397)

## Trading rules

- Investment universe: 28 commodity futures
- Filter: Exclude futures contracts with average trading volume below 1000 contracts
- Calculate idiosyncratic returns monthly using OLS regression (equation 4, page 9)
- Construct factor premiums in commodity futures using Fama & French approach (High minus Low)
    - Hedging Pressure (HP) factor portfolio:
        - Long 15% of futures with highest average HP
        - Short 15% of futures with lowest average HP
    - Term Structure factor portfolio (High roll yield – Low roll yield):
        - Long 15% of futures with highest average roll yield (backwardated market)
        - Short 15% of futures with lowest roll yield (contangoed market)
    - Value factor: Log of spot price 5 years ago divided by the most recent spot price
    - Size factor: Open interest multiplied by contract value
- Identify winners and losers by cumulating monthly residual returns over 3-month ranking period
    - Long top 7 futures
    - Short bottom 7 futures
- Portfolio: Equally weighted and rebalanced monthly

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1993-2014
- **Annual Return:** 17.5%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.59
- **Annual Standard Deviation:** 29.42%

## Python code

### Backtrader

```python
import backtrader
import pandas as pd
import numpy as np
import statsmodels.api as sm
from collections import defaultdict

class CommodityMomentum(backtrader.Strategy):
    def __init__(self):
        self.volume_filter = 1000
        self.top_percentage = 0.15

    def next(self):
        positions = defaultdict(int)

        for data in self.datas:
            if data.volume[-1] < self.volume_filter:
                continue
            positions[data._name] = data.close[0] - data.close[-1]

        sorted_positions = sorted(positions.items(), key=lambda x: x[1])
        long_positions = sorted_positions[-int(len(sorted_positions) * self.top_percentage):]
        short_positions = sorted_positions[:int(len(sorted_positions) * self.top_percentage)]

        for data in self.datas:
            if data._name in [p[0] for p in long_positions]:
                self.buy(data=data)
            elif data._name in [p[0] for p in short_positions]:
                self.sell(data=data)
            else:
                self.close(data=data)

def run_backtest():
    cerebro = backtrader.Cerebro()
    cerebro.addstrategy(CommodityMomentum)

    for symbol in commodity_symbols:
        data = backtrader.feeds.PandasData(dataname=get_data(symbol))
        cerebro.adddata(data, name=symbol)

    cerebro.broker.setcash(100000.0)
    cerebro.addsizer(backtrader.sizers.EqualWeight)
    cerebro.run()

def get_data(symbol):
    # Implement function to load data for the given symbol
    pass

if __name__ == "__main__":
    run_backtest()
```

This code snippet creates a simple Backtrader strategy based on the given trading rules. Note that the OLS regression and factor calculations are not implemented in this example. You’ll need to implement the `get_data` function to load historical data for each commodity symbol and include the factor calculations in the strategy.