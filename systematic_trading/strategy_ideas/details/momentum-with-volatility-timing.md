<div align="center">
  <h1>Momentum with Volatility Timing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3417360)

## Trading rules

- Investment universe: NYSE and AMEX stocks priced over $1
- Sort stocks into deciles by momentum
- Go long on top decile (6-month winners)
- Go short on bottom decile (6-month losers)
- Only trade if previous 12-month market return is positive
- Rebalance monthly with equal weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1925-1995
- **Annual Return:** 13.2%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.98
- **Annual Standard Deviation:** 9.4%

## Python code

### Backtrader

```python
import backtrader as bt

class MomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 126),
        ('ranking_period', 252),
        ('rebalance_period', 21),
        ('num_positions', 10)
    )

    def __init__(self):
        self.inds = dict()
        for d in self.datas:
            self.inds[d] = dict()
            self.inds[d]['momentum'] = bt.indicators.Momentum(d.close, period=self.params.momentum_period)
            self.inds[d]['market_return'] = bt.indicators.SumN(d.close / d.close(-self.params.ranking_period) - 1, period=self.params.ranking_period)

    def next(self):
        if self._daycounter % self.params.rebalance_period == 0:
            eligible_stocks = [d for d in self.datas if d.close[0] > 1]
            ranked_stocks = sorted(
                eligible_stocks,
                key=lambda s: self.inds[s]['momentum'][0],
                reverse=True
            )
            decile = len(ranked_stocks) // self.params.num_positions
            long_stocks = ranked_stocks[:decile]
            short_stocks = ranked_stocks[-decile:]
            for d in long_stocks:
                if self.inds[d]['market_return'][0] > 0:
                    self.order_target_percent(d, target=1.0 / self.params.num_positions)
            for d in short_stocks:
                if self.inds[d]['market_return'][0] > 0:
                    self.order_target_percent(d, target=-1.0 / self.params.num_positions)
            # Close positions not in long or short lists
            for d in self.datas:
                if d not in long_stocks + short_stocks:
                    self.order_target_percent(d, target=0.0)
        self._daycounter += 1

    def start(self):
        self._daycounter = 0

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add data feeds here

    cerebro.addstrategy(MomentumStrategy)
    cerebro.run()
```

Please note that the above code is just an implementation of the given trading rules and assumes that you have a working knowledge of Backtrader and have already set up the required data feeds for NYSE and AMEX stocks.