<div align="center">
  <h1>Buy-Side Competition and Momentum Profits</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3132378)

## Trading rules

- Obtain data on actively managed, open-ended U.S. equity mutual funds (e.g., from CRSP Survivor-Bias Free US Mutual Fund database)
- Exclude financial firms and firms with a price below $1 at the end of the month
- Compute the momentum competition metric:
    - At the end of month t-1, calculate returns over the interval (t-12, t-2) and standardize each stock’s return to a z-score
    - Locate each mutual fund in the one-dimensional momentum space based on the value-weighted location of the stocks it holds
    - Define two funds as competitors at time t if the interfund distance is less than or equal to a chosen parameter for target granularity
    - Compute the competition metric based on the similarity between a fund and its spatially proximate rivals
    - Average the competition measure across all funds holding a particular stock
- At the end of each month t-1:
    - Sort stocks into terciles by momentum competition
    - Sort stocks within the lowest competition tercile into quintile portfolios based on their traditional 12-month momentum
    - Long the highest quintile and short the lowest quintile
- Employ a value-weighted strategy and rebalance monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1980-2012
- **Annual Return:** 18%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.58
- **Annual Standard Deviation:** 23.95%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from scipy.stats import zscore

class MomentumCompetition(bt.Strategy):
    params = dict(
        granularity=1.0,
    )

    def __init__(self):
        self.terciles = None
        self.highest_quintile = None
        self.lowest_quintile = None

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            self.compute_momentum_competition()
            self.rank_stocks()
            self.rebalance_portfolio()

    def compute_momentum_competition(self):
        # Implement the logic to compute momentum competition metric here
        pass

    def rank_stocks(self):
        stocks = self.datas
        sorted_stocks = sorted(stocks, key=lambda stock: stock.competition_metric)
        tercile_size = len(sorted_stocks) // 3
        self.terciles = {
            "low": sorted_stocks[:tercile_size],
            "medium": sorted_stocks[tercile_size:2 * tercile_size],
            "high": sorted_stocks[2 * tercile_size:],
        }
        lowest_competition_stocks = self.terciles["low"]
        sorted_lowest_comp = sorted(lowest_competition_stocks, key=lambda stock: stock.momentum)
        quintile_size = len(sorted_lowest_comp) // 5
        self.highest_quintile = sorted_lowest_comp[-quintile_size:]
        self.lowest_quintile = sorted_lowest_comp[:quintile_size]

    def rebalance_portfolio(self):
        for stock in self.datas:
            if stock in self.highest_quintile:
                target_weight = stock.value_weight
                self.order_target_percent(stock, target=target_weight)
            elif stock in self.lowest_quintile:
                target_weight = -stock.value_weight
                self.order_target_percent(stock, target=target_weight)
            else:
                self.order_target_percent(stock, target=0.0)

cerebro = bt.Cerebro()

# Add data feeds and other settings to cerebro here

cerebro.addstrategy(MomentumCompetition)
results = cerebro.run()
```

Please note that the code provided is just a template and you will need to implement the logic to compute the momentum competition metric, as well as add data feeds and other settings to cerebro as required.