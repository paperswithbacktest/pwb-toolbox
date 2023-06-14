<div align="center">
  <h1>Industry Long-Term Return Reversal</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2620085)

## Trading rules

- Investment universe: ETFs tracking major stock industries (48 major industries used in the study)
- Timeframe: Quarterly sorting and 3-month holding period
- Step 1: Sort industries into quartiles based on past 120-month performance
- Step 2: Further sort the first (winners) and last (losers) quartiles based on 12-month performance
- Strategy: Buy long-term losers with strong recent short-term performance and sell long-term winners with weak recent short-term performance
- Portfolio: Equally weighted and rebalanced every 3 months

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1963-2013
- **Annual Return:** 9.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.3
- **Annual Standard Deviation:** 19.49%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class IndustryMomentumReversal(bt.Strategy):
    params = (
        ('lookback_long', 120),
        ('lookback_short', 12),
        ('holding_period', 3),
    )

    def __init__(self):
        self.month_counter = 0

    def next(self):
        self.month_counter += 1

        if self.month_counter % self.params.holding_period != 0:
            return

        performance_long = {}
        performance_short = {}

        for d in self.getdatanames():
            data = self.getdatabyname(d)

            if len(data) < self.params.lookback_long:
                continue

            performance_long[d] = (data.close[0] / data.close[-self.params.lookback_long]) - 1
            performance_short[d] = (data.close[0] / data.close[-self.params.lookback_short]) - 1

        sorted_by_long = sorted(performance_long.items(), key=lambda x: x[1])
        losers = sorted_by_long[:len(sorted_by_long) // 4]
        winners = sorted_by_long[-len(sorted_by_long) // 4:]
        losers_sorted_by_short = sorted(losers, key=lambda x: x[1], reverse=True)
        winners_sorted_by_short = sorted(winners, key=lambda x: x[1])

        selected_losers = [x[0] for x in losers_sorted_by_short[:len(losers_sorted_by_short) // 4]]
        selected_winners = [x[0] for x in winners_sorted_by_short[:len(winners_sorted_by_short) // 4]]

        positions = self.broker.get_value()

        for d in self.getdatanames():
            data = self.getdatabyname(d)
            position_size = positions / (len(selected_losers) + len(selected_winners))

            if d in selected_losers:
                self.order_target_value(data, target=position_size)
            elif d in selected_winners:
                self.order_target_value(data, target=-position_size)
            else:
                self.order_target_value(data, target=0)

cerebro = bt.Cerebro()

# Add data feeds here with appropriate names
# Example:
# data = bt.feeds.YahooFinanceData(dataname='SPY', fromdate=start_date, todate=end_date)
# cerebro.adddata(data, name='SPY')

cerebro.addstrategy(IndustryMomentumReversal)
cerebro.broker.setcash(1000000)
cerebro.broker.setcommission(commission=0.001)

print('Starting Portfolio Value:', cerebro.broker.getvalue())
cerebro.run()
print('Final Portfolio Value:', cerebro.broker.getvalue())
```