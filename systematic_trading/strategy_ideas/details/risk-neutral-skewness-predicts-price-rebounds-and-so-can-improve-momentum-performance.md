<div align="center">
  <h1>Risk Neutral Skewness Predicts Price Rebounds and so can Improve Momentum Performance</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3125124)

## Trading rules

- Investment universe: NYSE/AMEX/NASDAQ stocks priced above $5 and with a capitalization above 50% NYSE percentile
- Skewness proxy: Maximum daily return in the past month
- Monthly sorting process:
    - Sort stocks into quintiles based on expected skewness (max daily return)
    - Further sort stocks into quintiles based on past 12-month cumulative returns
- Momentum specification: 12-month formation period, 1-month holding period, skip 1 month
- Monthly portfolio construction:
    - Long position: Most negatively skewed winners
    - Short position: Most positively skewed losers
- Portfolio management: Equally weighted, rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1926-2011
- **Annual Return:** 14.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.46
- **Annual Standard Deviation:** 31.06%

## Python code

### Backtrader

Here is the Backtrader python code for the given trading rules:

```python
import backtrader as bt
import pandas as pd
import numpy as np

class SkewMomentumStrategy(bt.Strategy):
    params = (
        ('formation_period', 12),
        ('holding_period', 1),
        ('skip_period', 1),
        ('min_price', 5),
        ('capitalization_percentile', 0.5),
    )

    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['max_return'] = bt.indicators.Highest(d.close(-1) / d.close(-2), period=21)
            self.inds[d]['momentum'] = d.close / d.close(-self.p.formation_period) - 1

    def prenext(self):
        self.next()

    def next(self):
        if self._count % (self.p.holding_period + self.p.skip_period) != 0:
            return

        stocks = self.datas
        stocks = [d for d in stocks if d.close[0] > self.p.min_price]
        market_caps = np.array([d.market_cap[0] for d in stocks])
        threshold = np.percentile(market_caps, self.p.capitalization_percentile * 100)
        stocks = [d for d, mc in zip(stocks, market_caps) if mc >= threshold]

        skews = np.array([self.inds[d]['max_return'][0] for d in stocks])
        momentum = np.array([self.inds[d]['momentum'][0] for d in stocks])

        skew_quintiles = pd.qcut(skews, 5, labels=False)
        momentum_quintiles = pd.qcut(momentum, 5, labels=False)

        long_candidates = [d for d, sq, mq in zip(stocks, skew_quintiles, momentum_quintiles) if sq == 0 and mq == 4]
        short_candidates = [d for d, sq, mq in zip(stocks, skew_quintiles, momentum_quintiles) if sq == 4 and mq == 0]

        long_weight = 1.0 / len(long_candidates) if long_candidates else 0
        short_weight = -1.0 / len(short_candidates) if short_candidates else 0

        for d in long_candidates:
            self.order_target_percent(d, target=long_weight)

        for d in short_candidates:
            self.order_target_percent(d, target=short_weight)

        for d in set(self.datas) - set(long_candidates + short_candidates):
            self.order_target_percent(d, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SkewMomentumStrategy)

    # Load your custom data here (use NYSE, AMEX, and Nasdaq stocks with price > $5 and in the large subsample)
    # For example:
    # data = bt.feeds.PandasData(dataname=pd.read_csv('your_data.csv', index_col=0, parse_dates=True))
    # cerebro.adddata(data)

    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=99)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

This code defines a SkewMomentumStrategy class that implements the trading rules. The strategy calculates skewness proxies and past momentum for each stock, sorts them into quintiles, and constructs a long-short portfolio according to the specified criteria. The positions are equally weighted and rebalanced monthly.