<div align="center">
  <h1>Momentum Turning Points</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3489539)

## Trading rules

- Investment universe: U.S. excess value-weighted factor (Mkt-RF) from Kenneth French Data Library (CRSP firms in US listed on NYSE, AMEX, or NASDAQ with CRSP share code of 10 or 11)
- Fast momentum signal: 1-month momentum
- Slow momentum signal: 12-month momentum
- Blend signals using variable alfa: alfa * slow signal + (1 - alfa) * fast signal
- Alfa is state-dependent (bear, bull, correction, or rebound states)
    - Bear or bull states: alfa not important, set at 0.5
    - Correction or rebound states: alfa determined by maximization of Sharpe ratio in subsequent month
- Use historical estimates (sample averages) for expected values and probabilities
- Rebalance strategy monthly
- Strategy based on 77.5 years of data and applied to a 15-year trading period using average state-dependent alfa values

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2004-2018
- **Annual Return:** 6.11%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt

class DynamicMomentumStrategy(bt.Strategy):
    params = (
        ('fast_period', 1),
        ('slow_period', 12),
        ('rebalance_freq', 21),
    )

    def __init__(self):
        self.fast_momentum = bt.indicators.Momentum(self.data.close, period=self.params.fast_period)
        self.slow_momentum = bt.indicators.Momentum(self.data.close, period=self.params.slow_period)
        self.counter = 0

    def next(self):
        self.counter += 1
        if self.counter % self.params.rebalance_freq == 0:
            alfa = self.calculate_alfa()
            blended_signal = alfa * self.slow_momentum[0] + (1 - alfa) * self.fast_momentum[0]
            if blended_signal > 0:
                self.order_target_percent(target=1.0)
            else:
                self.order_target_percent(target=0.0)

    def calculate_alfa(self):
        # Determine the market state and calculate alfa accordingly
        # This function should be implemented based on the research paper,
        # using historical estimates (sample averages) for expected values and probabilities
        # and the maximization of Sharpe ratio in the subsequent month for correction or rebound states
        pass

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    data = bt.feeds.YahooFinanceData(dataname='^GSPC', fromdate=datetime(2003, 1, 1), todate=datetime(2018, 12, 31))
    cerebro.adddata(data)
    cerebro.addstrategy(DynamicMomentumStrategy)
    cerebro.run()
```

Please note that this code is only a starting point for your strategy implementation. You will need to implement the `calculate_alfa` function based on the research paper to determine the market state and calculate alfa accordingly. Also, make sure to load the appropriate data for the investment universe (U.S. excess value-weighted factor (Mkt-RF) from Kenneth French Data Library) instead of the example used in the code.