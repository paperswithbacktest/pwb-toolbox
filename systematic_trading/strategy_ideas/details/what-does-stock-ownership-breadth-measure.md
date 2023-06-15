<div align="center">
  <h1>What Does Stock Ownership Breadth Measure?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1571694)

## Trading rules

- Investment universe: All NYSE, AMEX, and NASDAQ stocks priced above $1
- Quarterly division: Divide stocks into quintiles, focus on highest turnover quintile
- Data source: 13F filings for institutional investor ownership
- Assumption: Non-institutional ownership represents individual ownership
- Calculation: Determine institutional to individual ownership turnover (InstTurnIndiv)
    - Aggregate institutional shares per quarter
    - Calculate quarterly change in aggregate shares
    - Average shares traded over recent eight quarters
    - Divide average by total institutional shares held in that period
- Stock sorting: Rank stocks into deciles based on InstTurnIndiv
- Positioning: Long on lowest InstTurnIndiv decile, short on highest InstTurnIndiv decile
- Rebalancing: Quarterly with equal stock weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1983-2007
- **Annual Return:** 15%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.52
- **Annual Standard Deviation:** 21%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class InstTurnIndivStrategy(bt.Strategy):
    def __init__(self):
        self.inst_turnover = {}
        self.rankings = []

    def prenext(self):
        self.next()

    def next(self):
        if self.datas[0].datetime.date(0).month % 3 == 0 and self.datas[0].datetime.date(-1).month % 3 != 0:
            self.calculate_inst_turnover()
            self.rank_stocks()
            self.rebalance()

    def calculate_inst_turnover(self):
        self.inst_turnover.clear()
        for d in self.datas:
            data = pd.DataFrame({'price': d.close.array})
            data['institutional_shares'] = d.institutional_shares.array
            data['quarterly_change'] = data['institutional_shares'].diff().fillna(0)
            data['recent_eight_quarters'] = data['quarterly_change'].rolling(window=8).mean().fillna(0)
            inst_turnover = data['recent_eight_quarters'].iloc[-1] / data['institutional_shares'].iloc[-1]
            self.inst_turnover[d] = inst_turnover

    def rank_stocks(self):
        self.rankings = sorted(self.datas, key=lambda x: self.inst_turnover[x])

    def rebalance(self):
        decile_size = len(self.rankings) // 10
        for i, d in enumerate(self.rankings[:decile_size]):
            target_size = self.broker.getvalue() / decile_size
            self.order_target_value(d, target_size)

        for i, d in enumerate(self.rankings[-decile_size:]):
            target_size = -self.broker.getvalue() / decile_size
            self.order_target_value(d, target_size)

cerebro = bt.Cerebro()
# Add data feeds
for symbol in investment_universe:
    data = MyCustomDataFeed(dataname=symbol)
    if data.close[0] > 1:
        cerebro.adddata(data)

cerebro.addstrategy(InstTurnIndivStrategy)
cerebro.broker.setcash(100000.0)
cerebro.run()
cerebro.plot()
```

Please note that you need to replace `investment_universe` with the list of stock symbols from NYSE, AMEX, and NASDAQ that are priced above $1. Additionally, you need to implement the `MyCustomDataFeed` class that loads the 13F filings data and adds it as a line to the data feed.