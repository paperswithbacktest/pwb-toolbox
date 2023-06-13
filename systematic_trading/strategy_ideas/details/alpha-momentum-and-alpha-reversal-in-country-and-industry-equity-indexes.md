<div align="center">
  <h1>Alpha Momentum and Alpha Reversal in Country and Industry Equity Indexes</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3235350)

## Trading rules

- Investment universe: 51 country indexes
- Compute alphas: Use simple CAPM model (Equation 1, pg. 13)
- Calculate alpha score: Scale alphas by return volatility (standard deviation or Equation 5, pg. 14)
- Determine alpha momentum (month t): Use volatility-adjusted alpha from months t-12 to t-1
- Rank indexes: Based on alpha score
- Positioning: Long highest quintile, short lowest quintile
- Strategy: Value-weighted, monthly rebalancing (also tested: equally-weighted)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1973-2018
- **Annual Return:** 6.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.31
- **Annual Standard Deviation:** 20.02%

## Python code

### Backtrader

```python
import backtrader as bt

class AlphaMomentum(bt.Strategy):
    params = (
        ('lookback', 12),
    )

    def __init__(self):
        self.alphas = {}
        self.market_rets = {}
        self.scores = {}

    def next(self):
        # Compute alphas and returns for each index
        for d in self.getdatanames():
            data = self.getdatabyname(d)

            # Compute returns and alphas using simple CAPM model
            market_ret = data.close[0] / data.close[-1] - 1
            self.market_rets[d] = market_ret
            alpha = market_ret - (self._owner.broker.getvalue() / self._owner.broker.startingcash - 1)
            self.alphas[d] = alpha

            # Calculate alpha score
            alpha_vol = bt.indicators.StdDev(self.alphas[d], period=self.params.lookback)
            self.scores[d] = alpha / alpha_vol

        # Determine alpha momentum and rank indexes
        sorted_indexes = sorted(self.scores, key=self.scores.get, reverse=True)
        top_quintile = sorted_indexes[:len(sorted_indexes) // 5]
        bottom_quintile = sorted_indexes[-(len(sorted_indexes) // 5):]

        # Positioning: Long highest quintile, short lowest quintile
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            position_size = self.broker.getvalue() / (len(top_quintile) + len(bottom_quintile))

            if d in top_quintile:
                self.order_target_value(data, target=position_size)
            elif d in bottom_quintile:
                self.order_target_value(data, target=-position_size)
            else:
                self.order_target_value(data, target=0)

        # Rebalance monthly
        self.notify_timer(when=bt.Timer.SESSION_END)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add investment universe
    for index in range(51):
        data = bt.feeds.GenericCSVData(dataname=f'index_{index}.csv')
        cerebro.adddata(data, name=f'index_{index}')

    # Add strategy
    cerebro.addstrategy(AlphaMomentum)

    # Set initial cash and run backtest
    cerebro.broker.set_cash(100000)
    cerebro.run()
```

Please note that this is a simplified example of the trading rules provided, and you may need to adjust the code to fit your specific data and requirements. Additionally, the code assumes you have separate CSV files for each of the 51 country indexes.