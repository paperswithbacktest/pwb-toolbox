<div align="center">
  <h1>Basis-momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2587784)

## Trading rules

- Investment universe: 32 commodity futures
- Monthly sorting based on 12-month momentum difference between first- and second-nearby contracts
    - High4: Top 4 commodities with highest ranked signal
    - Low4: Bottom 4 commodities with lowest ranked signal
    - Mid: All other commodities
- Long positions: 4 commodities from High4 group
- Short positions: 4 commodities from Low4 group
- Equal weighting for portfolio
- Monthly rebalancing

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1960-2014
- **Annual Return:** 18.38%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.92
- **Annual Standard Deviation:** 19.98%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class MomentumRank(bt.Analyzer):
    def __init__(self):
        self.momentum_rank = []

    def start(self):
        self.rets = pd.DataFrame()

    def next(self):
        # Get the returns of all data feeds
        rets = pd.Series({data._name: data.close[0] / data.close[-1] - 1 for data in self.datas})
        self.rets = self.rets.append(rets, ignore_index=True)
        if len(self.rets) >= 12:
            momentum = self.rets.iloc[-12:].sum()
            momentum_rank = momentum.nlargest(4).index.tolist() + momentum.nsmallest(4).index.tolist()
            self.momentum_rank = momentum_rank

class MomentumStrategy(bt.Strategy):
    def __init__(self):
        self.mom_ranker = self.analyzers.MomentumRank

    def next(self):
        # Get the ranked instruments
        momentum_rank = self.mom_ranker.get_analysis()
        for data in self.datas:
            pos = self.getposition(data).size
            if data._name in momentum_rank[:4]:  # Top 4 -> Long
                if pos == 0:
                    self.order_target_percent(data, target=1.0/4)
            elif data._name in momentum_rank[-4:]:  # Bottom 4 -> Short
                if pos == 0:
                    self.order_target_percent(data, target=-1.0/4)
            else:  # No position for Mid group
                self.close(data)

cerebro = bt.Cerebro()

# Add data feeds
for symbol in symbols:
    data = bt.feeds.YourDataFeed(dataname=symbol)
    cerebro.adddata(data)

# Add strategy
cerebro.addstrategy(MomentumStrategy)

# Add MomentumRank analyzer
cerebro.addanalyzer(MomentumRank)

# Add broker and set leverage
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_coc(True)

# Add monthly rebalancing timer
cerebro.addsizer(bt.sizers.EqualWeight)
cerebro.add_timer(bt.timer.SESSION_END, monthdays=[1], monthcarry=True)

# Run the strategy
results = cerebro.run()
```