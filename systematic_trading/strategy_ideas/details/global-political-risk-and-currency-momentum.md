<div align="center">
  <h1>Global Political Risk and Currency Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2517400)

## Trading rules

- Establish an investment universe of 10-20 currencies
- Identify top 3 currencies with highest 12-month momentum against USD for long positions
- Identify bottom 3 currencies with lowest 12-month momentum against USD for short positions
- Allocate unused cash to overnight rates
- Rebalance positions on a monthly basis

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1989-2010
- **Annual Return:** 6.48%
- **Maximum Drawdown:** -21.63%
- **Sharpe Ratio:** 0.65
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class CurrencyMomentum(bt.Strategy):
    params = dict(
        momentum_period=12,
        num_long=3,
        num_short=3,
    )

    def __init__(self):
        self.monthly_rebalancer = bt.indicators.TimeReturn(
            self.data.close,
            bt.TimeFrame.Months,
            compression=self.p.momentum_period,
        )

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            currencies_returns = {
                data._name: data.monthly_rebalancer[0]
                for data in self.datas
            }
            sorted_currencies = sorted(
                currencies_returns.items(), key=lambda x: x[1], reverse=True
            )
            long_currencies = sorted_currencies[: self.p.num_long]
            short_currencies = sorted_currencies[-self.p.num_short:]
            for data in self.datas:
                if data._name in [x[0] for x in long_currencies]:
                    self.order_target_percent(data=data, target=1 / self.p.num_long)
                elif data._name in [x[0] for x in short_currencies]:
                    self.order_target_percent(data=data, target=-1 / self.p.num_short)
                else:
                    self.order_target_percent(data=data, target=0)

cerebro = bt.Cerebro()
# Add your currency data feeds here
# cerebro.adddata(data)
cerebro.addstrategy(CurrencyMomentum)
cerebro.run()
```

This code snippet assumes that you have already set up a Backtrader environment and properly prepared your currency data feeds.