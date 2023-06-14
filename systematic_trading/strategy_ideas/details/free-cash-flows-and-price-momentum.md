<div align="center">
  <h1>Free Cash Flows and Price Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3207098)

## Trading rules

- Investment universe: Common stocks on NYSE/AMEX (excluding stocks priced below $5)
- Divide stocks into low and high bid-ask spread portfolios
- Perform double sorting on low bid-ask spread portfolio based on:
    - Past 6-month returns (momentum sorting)
    - Accruals
- Assign stocks to one of five portfolios for both sorting criteria
- Long position: Momentum winner portfolio with lowest accruals
- Short position: Momentum loser portfolio with highest accruals
- Holding period: Six months (month 2 to 7), with a one-month gap between formation and holding periods (month 1)
- Overlapping portfolios
- Portfolio weighting: Equally weighted
- Rebalancing: Monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1965-2015
- **Annual Return:** 10.43%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.59
- **Annual Standard Deviation:** 10.82%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class AccrualMomentum(bt.Strategy):
    params = (
        ('momentum_period', 6),
        ('formation_period', 1),
        ('holding_period', 6),
        ('n_portfolios', 5),
        ('stock_price_filter', 5),
    )

    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['momentum'] = bt.indicators.PctChange(d.close, period=self.params.momentum_period)
            self.inds[d]['accruals'] = None  # Accruals data should be preprocessed and included as an extra line in the data feed

    def prenext(self):
        self.next()

    def next(self):
        if self._get_period() % (self.params.holding_period + self.params.formation_period) != 0:
            return

        momentum_data = []
        for d in self.datas:
            if self._get_period() - self.params.momentum_period - self.params.formation_period >= 0:
                if d.close[0] > self.params.stock_price_filter:
                    momentum_data.append((d, self.inds[d]['momentum'][0], self.inds[d]['accruals'][0]))

        sorted_momentum = sorted(momentum_data, key=lambda x: x[1], reverse=True)
        sorted_accruals = sorted(momentum_data, key=lambda x: x[2])
        portfolio_size = len(sorted_momentum) // self.params.n_portfolios
        long_stocks = sorted_momentum[:portfolio_size]
        long_stocks = sorted(long_stocks, key=lambda x: x[2])[:portfolio_size]
        short_stocks = sorted_momentum[-portfolio_size:]
        short_stocks = sorted(short_stocks, key=lambda x: x[2], reverse=True)[:portfolio_size]
        long_cash_per_stock = self.broker.get_cash() / len(long_stocks)
        short_cash_per_stock = self.broker.get_cash() / len(short_stocks)

        # Open positions
        for d, _, _ in long_stocks:
            self.order_target_value(d, target=long_cash_per_stock)

        for d, _, _ in short_stocks:
            self.order_target_value(d, target=-short_cash_per_stock)

        # Close positions not in the new portfolio
        for d, pos in self.getpositions().items():
            if d not in [x[0] for x in long_stocks] and pos.size > 0:
                self.order_target_value(d, target=0)

            if d not in [x[0] for x in short_stocks] and pos.size < 0:
                self.order_target_value(d, target=0)

    def _get_period(self):
        return len(self.datas[0]) - self.datas[0].buflen()
```

Please note that this code assumes that the accruals data is preprocessed and included as an extra line in the data feed. You should also have the data for common stocks on NYSE/AMEX loaded into the data feeds.