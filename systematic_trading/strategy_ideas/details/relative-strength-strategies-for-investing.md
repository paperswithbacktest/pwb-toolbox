<div align="center">
  <h1>Relative Strength Strategies for Investing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585517)

## Trading rules

- Investment Universe: 5 ETFs (SPY, EFA, BND, VNQ, GSG)
- Select top 3 ETFs with highest 12-month momentum
- Allocate equal weights to chosen ETFs
- Hold portfolio for one month
- Rebalance monthly

## Statistics

- **Markets Traded:** Bonds, commodities, equities, REITs
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1973-2009
- **Annual Return:** 15%
- **Maximum Drawdown:** -12.95%
- **Sharpe Ratio:** 1.15
- **Annual Standard Deviation:** 9.6%

## Python code

### Backtrader

```python
import backtrader as bt

class MomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 12),
        ('rebalance_days', 30),
    )

    def __init__(self):
        self.etfs = []
        self.momentum = {}
        self.inds = {}

        for d in self.getdatanames():
            data = self.getdatabyname(d)
            self.etfs.append(data)
            self.momentum[data] = 0
            self.inds[data] = bt.indicators.ROC(data.close, period=self.params.momentum_period)

    def next(self):
        if self.datetime.day() % self.params.rebalance_days == 0:

            for data in self.etfs:
                self.momentum[data] = self.inds[data][0]

            sorted_etfs = sorted(self.etfs, key=lambda x: self.momentum[x], reverse=True)
            top_etfs = sorted_etfs[:3]
            target_weight = 1.0 / len(top_etfs)

            for data in self.etfs:
                if data in top_etfs:
                    self.order_target_percent(data, target_weight)
                else:
                    self.order_target_percent(data, 0)

cerebro = bt.Cerebro()
# Add data feeds for SPY, EFA, BND, VNQ, GSG here
cerebro.adddata(spy_data, name='SPY')
cerebro.adddata(efa_data, name='EFA')
cerebro.adddata(bnd_data, name='BND')
cerebro.adddata(vnq_data, name='VNQ')
cerebro.adddata(gsg_data, name='GSG')
cerebro.addstrategy(MomentumStrategy)
results = cerebro.run()