<div align="center">
  <h1>Twin Momentum: Fundamental Trends Matter</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2894068)

## Trading rules

- Investment universe: NYSE, AMEX, NASDAQ stocks; price > $5; excludes financial companies & regulated industries
- Price momentum: Rank stocks by 6-month returns; top decile = winners, bottom decile = losers
- Earnings momentum (SUE): Calculate standardized unexpected earnings; top decile = winners, bottom decile = losers
- Revenue momentum (SURGE): Calculate standardized unexpected revenue growth; top decile = winners, bottom decile = losers
- Price-Earnings-Revenue Combined Momentum: Buy high momentum stocks, sell low momentum stocks
- Holding period: 6 months, with 1/6 of the portfolio rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1974-2007
- **Annual Return:** 20.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.03
- **Annual Standard Deviation:** 16.13%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class MomentumRank(bt.ind.OperationN):
    lines = ('rank',)
    params = dict(period=126)

    def next(self):
        rets = np.log(self.data.get(size=self.p.period))
        rank = pd.Series(rets).rank(pct=True)[self.p.period - 1]
        self.lines.rank[0] = rank

class CombinedMomentum(bt.Strategy):
    params = dict(
        price_momentum_period=126,
        holding_period=6,
        monthly_rebalance=1,
        reserve_cash=0.05
    )

    def __init__(self):
        self.price_momentum = MomentumRank(self.data.close, period=self.p.price_momentum_period)
        self.earnings_momentum = self.data.SUE
        self.revenue_momentum = self.data.SURGE

    def next(self):
        if len(self) % (self.p.holding_period * self.p.monthly_rebalance) == 0:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        self.rankings = list(self.datas)
        self.rankings.sort(key=lambda x: (x.price_momentum.rank[0], x.earnings_momentum[0], x.revenue_momentum[0]), reverse=True)
        num_stocks = int(len(self.datas) * (1 - self.p.reserve_cash))
        target_value = self.broker.getvalue() / num_stocks

        for i, d in enumerate(self.rankings[:num_stocks]):
            self.order_target_value(d, target_value)

        for d in self.rankings[num_stocks:]:
            self.close(data=d)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Load data and add to Cerebro
    # Replace `your_stock_data_list` with your actual stock data list
    for stock_data in your_stock_data_list:
        data = bt.feeds.PandasData(dataname=stock_data)
        cerebro.adddata(data)

    cerebro.addstrategy(CombinedMomentum)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
```

Please note that this code assumes you have already preprocessed the data and calculated SUE (Standardized Unexpected Earnings) and SURGE (Standardized Unexpected Revenue Growth) for each stock. Replace `your_stock_data_list` with the list of stock data that meet the investment universe criteria (NYSE, AMEX, NASDAQ, price > $5, excluding financial companies and regulated industries).