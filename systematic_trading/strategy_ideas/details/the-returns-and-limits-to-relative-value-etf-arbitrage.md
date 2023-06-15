<div align="center">
  <h1>The Returns and Limits to Relative-Value ETF Arbitrage</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2816849)

## Trading rules

- Investment universe: 22 international ETFs
- Create a normalized cumulative total return index for each ETF (including dividends)
- Set starting price to $1 during 120-day formation period (price normalization)
- Calculate pair’s distance as sum of squared deviations between two normalized price series
- Select top 5 pairs with smallest distance for 20-day trading period
- Monitor strategy daily; open trade when divergence between pairs exceeds 0.5x historical standard deviation
- Go long on undervalued ETF, short on overvalued ETF
- Exit trade when pair converges or after 20 days (if no convergence)
- Weight pairs equally and rebalance portfolio daily

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1996-2009
- **Annual Return:** 20.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.66
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from itertools import combinations

class PairsTrading(bt.Strategy):
    params = (
        ('formation_period', 120),
        ('trading_period', 20),
        ('num_pairs', 5),
        ('std_dev_threshold', 0.5),
    )

    def __init__(self):
        self.counter = 0
        self.pairs = []

    def next(self):
        self.counter += 1
        if self.counter < self.params.formation_period:
            return
        if self.counter % self.params.trading_period == 0:
            self.select_pairs()
        for data1, data2 in self.pairs:
            spread = self.calculate_spread(data1, data2)
            std_dev = np.std(spread)
            position1 = self.getposition(data1).size
            position2 = self.getposition(data2).size
            if abs(spread[-1]) > self.params.std_dev_threshold * std_dev:
                if spread[-1] > 0 and position1 == 0 and position2 == 0:
                    self.buy(data1)
                    self.sell(data2)
                elif spread[-1] < 0 and position1 == 0 and position2 == 0:
                    self.sell(data1)
                    self.buy(data2)
            elif abs(spread[-1]) <= std_dev or self.counter % self.params.trading_period == 0:
                if position1 != 0:
                    self.close(data1)
                if position2 != 0:
                    self.close(data2)

    def select_pairs(self):
        distances = {}
        symbols = self.datas
        for pair in combinations(symbols, 2):
            data1 = pair[0].get(size=self.params.formation_period)
            data2 = pair[1].get(size=self.params.formation_period)
            normalized_data1 = data1 / data1[0]
            normalized_data2 = data2 / data2[0]
            distance = np.sum((normalized_data1 - normalized_data2) ** 2)
            distances[pair] = distance
        sorted_pairs = sorted(distances.items(), key=lambda x: x[1])
        self.pairs = [pair[0] for pair in sorted_pairs[:self.params.num_pairs]]

    def calculate_spread(self, data1, data2):
        data1_prices = pd.Series(data1.get(size=self.params.formation_period))
        data2_prices = pd.Series(data2.get(size=self.params.formation_period))
        data1_normalized = data1_prices / data1_prices.iloc[0]
        data2_normalized = data2_prices / data2_prices.iloc[0]
        spread = data1_normalized - data2_normalized
        return spread

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PairsTrading)
    # Add ETF data here
    # Example: cerebro.adddata(bt.feeds.YahooFinanceData(dataname='SPY', fromdate=start, todate=end))
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.EqualWeight)
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Remember to add the desired ETF data feeds in the section commented in the code.