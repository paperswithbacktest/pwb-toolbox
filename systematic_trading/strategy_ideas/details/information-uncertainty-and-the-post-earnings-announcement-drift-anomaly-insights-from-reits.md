<div align="center">
  <h1>Information Uncertainty and the Post-Earnings-Announcement Drift Anomaly: Insights from REITs</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1633542)

## Trading rules

- Investment universe: All US REITs listed on NYSE, NASDAQ, and AMEX
- Sort REITs into earnings surprise deciles based on earnings surprise magnitude
- Calculate earnings surprises using seasonal random walk model
    - Compare current quarter EPS to EPS lagged four quarters
    - Scale difference by stock price 45 days before earnings announcement
- Go long on high earnings surprise decile, short on low earnings surprise decile
- Hold REITs for 60 days, starting one day after earnings announcement
- Rebalance portfolio approximately quarterly
- Weight REITs equally within the portfolio

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1982-2008
- **Annual Return:** 21%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.28
- **Annual Standard Deviation:** 13.25%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class EarningsSurprise(bt.Strategy):
    params = (
        ('hold_days', 60),
        ('rebalance_days', 90),
        ('deciles', 10),
    )

    def __init__(self):
        self.order_dict = dict()

    def next(self):
        if len(self.datas) < max(self.params.hold_days, self.params.rebalance_days):
            return

        if self.datetime.date(0) % self.params.rebalance_days == 0:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        earnings_surprises = self.calculate_earnings_surprises()
        sorted_reits = earnings_surprises.sort_values(ascending=False)
        decile_size = len(sorted_reits) // self.params.deciles
        long_reits = sorted_reits[:decile_size].index
        short_reits = sorted_reits[-decile_size:].index

        for data in self.datas:
            if data._name in long_reits:
                self.order_target_percent(data, target=1 / len(long_reits))
            elif data._name in short_reits:
                self.order_target_percent(data, target=-1 / len(short_reits))
            else:
                self.order_target_percent(data, target=0)

    def calculate_earnings_surprises(self):
        earnings_surprises = pd.Series(index=[d._name for d in self.datas])

        for data in self.datas:
            eps_current = data.eps[0]
            eps_lagged = data.eps[-4]
            price_45_days_ago = data.close[-45]
            surprise = (eps_current - eps_lagged) / price_45_days_ago
            earnings_surprises[data._name] = surprise

        return earnings_surprises

class PandasData_EPS(bt.feeds.PandasData):
    lines = ('eps',)
    params = (('eps', -1),)

cerebro = bt.Cerebro()

reits_data = {}  # Load REITs historical data with EPS information

for reit, data in reits_data.items():
    data_feed = PandasData_EPS(dataname=data)
    cerebro.adddata(data_feed, name=reit)

cerebro.addstrategy(EarningsSurprise)
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)

results = cerebro.run()
```

This code assumes you have historical data for each REIT with EPS information. Replace `reits_data` with your actual data.