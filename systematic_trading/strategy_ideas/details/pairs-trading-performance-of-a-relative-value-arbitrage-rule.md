<div align="center">
  <h1>Pairs Trading: Performance of a Relative Value Arbitrage Rule</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615)

## Trading rules

- Stock selection from NYSE, AMEX, and NASDAQ, excluding illiquid stocks
- Creation of cumulative total return index for each stock (including dividends)
- Price normalization by setting starting price to $1 during formation period
- Formation of pairs over a 12-month period, followed by a 6-month trading period
- Identification of matching partners based on minimized sum of squared deviations between normalized price series
- Selection of top 20 pairs with smallest historical distance measure for trading
- Opening of long-short positions when pair prices diverge by two standard deviations
- Closing of positions when prices revert

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1962-2002
- **Annual Return:** 11.16%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.22
- **Annual Standard Deviation:** 5.85%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from scipy.spatial.distance import cdist

class PairsTradingStrategy(bt.Strategy):
    params = dict( formation_period=252, # 12-month formation period
        trading_period=126, # 6-month trading period
        num_pairs=20, # top 20 pairs
        entry_threshold=2, # open positions when prices diverge by 2 standard deviations
        exit_threshold=0, # close positions when prices revert
    )

    def __init__(self):
        self.formation_period = self.params.formation_period
        self.trading_period = self.params.trading_period
        self.num_pairs = self.params.num_pairs
        self.entry_threshold = self.params.entry_threshold
        self.exit_threshold = self.params.exit_threshold

        self.pair_candidates = []
        self.current_pairs = []
        self.in_positions = []

    def prenext(self):
        self.next()

    def next(self):
        if len(self.data) <= (self.formation_period + self.trading_period):
            return

        if self.timereturn() % (self.formation_period + self.trading_period) == 0:
            self.pair_candidates = self.generate_pair_candidates()
            self.current_pairs = self.select_pairs(self.pair_candidates, self.num_pairs)
            self.in_positions = [False] * len(self.current_pairs)

        if not self.current_pairs:
            return

        for i, (d1, d2) in enumerate(self.current_pairs):
            z_score = self.calculate_z_score(d1, d2)

            if not self.in_positions[i] and abs(z_score) >= self.entry_threshold:
                self.buy(data=d1)
                self.sell(data=d2)
                self.in_positions[i] = True

            elif self.in_positions[i] and abs(z_score) <= self.exit_threshold:
                self.sell(data=d1)
                self.buy(data=d2)
                self.in_positions[i] = False

    def generate_pair_candidates(self):
        stocks = [d for d in self.datas]
        scaler = MinMaxScaler()
        data_scaled = scaler.fit_transform([d.get(size=self.formation_period) for d in stocks])
        distance_matrix = cdist(data_scaled, data_scaled, 'sqeuclidean')
        pair_candidates = np.argwhere(distance_matrix < np.percentile(distance_matrix, 5))
        return [(stocks[i], stocks[j]) for i, j in pair_candidates if i < j]

    def select_pairs(self, pair_candidates, num_pairs):
        pair_distances = [(d1, d2, self.calculate_sum_of_squared_deviations(d1, d2)) for d1, d2 in pair_candidates]
        sorted_pairs = sorted(pair_distances, key=lambda x: x[2])
        return [p[0:2] for p in sorted_pairs[:num_pairs]]

    def calculate_sum_of_squared_deviations(self, d1, d2):
        price1 = d1.get(size=self.formation_period)
        price2 = d2.get(size=self.formation_period)
        return np.sum((price1 / price1[0] - price2 / price2[0]) ** 2)

    def calculate_z_score(self, d1, d2):
        spread = np.log(d1.get(size=self.trading_period)) - np.log(d2.get(size=self.trading_period))
        mean_spread = np.mean(spread)
        std_spread = np.std(spread)
        return (spread[-1] - mean_spread) / std_spread

    def timereturn(self):
        return (len(self.data))
```