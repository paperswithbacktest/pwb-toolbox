<div align="center">
  <h1>Betting Against Correlation: Testing Theories of the Low-Risk Effect</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2913508)

## Trading rules

- Utilize the entire US stock universe for investment
- Rank stocks in ascending order based on previous month’s estimated volatility
- Assign stocks to one of five quintiles
- Within each quintile, classify stocks into low or high market correlation portfolios
- Rank-weight stocks by correlation within respective portfolios
- Implement long positions for low-correlation stocks and short positions for high-correlation stocks in each quintile
- Allocate equal weights to each quintile
- Rebalance the portfolio on a monthly basis

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1963-2015
- **Annual Return:** 12.28%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.93
- **Annual Standard Deviation:** 13.2%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd

class BettingAgainstCorrelation(bt.Strategy):
    params = (
        ('n_quintiles', 5),
    )

    def __init__(self):
        self.rank = {}
        self.data_close = self.datas

    def next(self):
        if self._get_market_index() % 21 != 0:  # Rebalance monthly
            return
        self.rank_stocks()
        self.create_quintiles()
        self.rank_correlation()
        self.set_positions()

    def _get_market_index(self):
        return len(self.data_close[0])

    def rank_stocks(self):
        volatilities = [bt.indicators.StdDev(d.close, period=21) for d in self.data_close]
        self.rank = sorted(self.data_close, key=lambda d: volatilities[self.data_close.index(d)][0])

    def create_quintiles(self):
        self.quintiles = np.array_split(self.rank, self.params.n_quintiles)

    def rank_correlation(self):
        self.correlations = []
        for quintile in self.quintiles:
            correlations = []
            for data in quintile:
                correlation = bt.indicators.Correlation(data.close, bt.indicators.Market(data.close), period=21)
                correlations.append((data, correlation[0]))
            correlations.sort(key=lambda x: x[1])
            self.correlations.append(correlations)

    def set_positions(self):
        for quintile_correlations in self.correlations:
            n = len(quintile_correlations)
            half_n = n // 2
            for i, (data, _) in enumerate(quintile_correlations):
                if i < half_n:
                    self.order_target_percent(data, target=1.0 / (self.params.n_quintiles * half_n))
                else:
                    self.order_target_percent(data, target=-1.0 / (self.params.n_quintiles * half_n))

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for US stocks
    # cerebro.adddata(...)

    cerebro.addstrategy(BettingAgainstCorrelation)
    cerebro.run()
```