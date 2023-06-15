<div align="center">
  <h1>Size Matters Everywhere: Decomposing the Small Country and Small Industry Premia</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3035891)

## Trading rules

- Investment universe: local supersector indices (936 industries, 51 countries)
    - Includes developed, emerging, and frontier markets
    - Based on Industry Classification Benchmark (ICB)
    - 19 industries covered
- Initial market data in local currencies, converted to USD
- Risk-free rate proxy: one-month Treasury bill rate
- Long-short zero-investment factor portfolio construction
    - Components weighted based on de-meaned value of return predictive variables
- Industry index weighting:
    - Proportional to cross-sectional rank based on MV i minus cross-sectional average of MV
    - Scaled with a factor to maintain one dollar long and one dollar short
- Portfolio weights sum to zero (zero-investment)
- Return on factor portfolio: sum of weights multiplied by corresponding returns
- Monthly portfolio rebalancing

## Statistics

- **Markets Traded:** ETFs, stocks
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1973-2017
- **Annual Return:** 14.03%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.83
- **Annual Standard Deviation:** 12.09%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.indicators as btind
import numpy as np

class SmallIndustryPremia(bt.Strategy):
    params = dict(
        rebalancing_period=21  # Monthly rebalancing
    )

    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['mv'] = btind.MarketCap(d)
        self.rebalancing_counter = 0

    def prenext(self):
        # Call next() even when data is not available for all tickers
        self.next()

    def next(self):
        if self.rebalancing_counter % self.params.rebalancing_period == 0:
            self.rebalance_portfolio()
        self.rebalancing_counter += 1

    def rebalance_portfolio(self):
        mvs = np.array([self.inds[d]['mv'][0] for d in self.datas], dtype=np.float)
        ranks = (-mvs).argsort()
        longs = ranks[:len(ranks)//2]
        shorts = ranks[len(ranks)//2:]

        # Calculate scaling factor
        scaling_factor = 1 / (np.sum(mvs[longs]) - np.sum(mvs[shorts]))

        for i, d in enumerate(self.datas):
            if i in longs:
                target_weight = self.inds[d]['mv'][0] * scaling_factor
            elif i in shorts:
                target_weight = -self.inds[d]['mv'][0] * scaling_factor
            else:
                target_weight = 0
            self.order_target_percent(d, target=target_weight)
```

Please note that this implementation assumes that you have the market cap data in the form of a custom MarketCap indicator, and the market data for all the tickers has been added to the strategy. The given code is a basic implementation of the strategy and might need further adjustments to fit your specific data and requirements.