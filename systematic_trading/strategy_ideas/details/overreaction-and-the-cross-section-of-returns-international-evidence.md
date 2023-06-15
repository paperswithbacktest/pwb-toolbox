<div align="center">
  <h1>Overreaction and the Cross-Section of Returns: International Evidence</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2800188)

## Trading rules

- Investment universe: 26 emerging market countries
- Monthly ranking based on past 60-month performance
    - Top 25%: Late-stage winners (LW)
    - Bottom 25%: Late-stage losers (LL)
- Rank countries within each subgroup by 6-month momentum
- Long positions: Top 50% of best 6-month momentum in LL group
- Short positions: Bottom 50% of worst 6-month momentum in LW group
- Equal weighting for each country
- Hold positions for 6 months
- Monthly portfolio rebalance (1/6th of the portfolio each month)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1988-2011
- **Annual Return:** 15.94%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.41
- **Annual Standard Deviation:** 28.89%

## Python code

### Backtrader

```python
import backtrader as bt

class EmergingMarketStrategy(bt.Strategy):
    def __init__(self):
        self.month_counter = 0
        self.rebalance_period = 6

    def next(self):
        # Check if it's time to rebalance the portfolio
        self.month_counter += 1
        if self.month_counter % self.rebalance_period != 0:
            return

        # Calculate 60-month performance
        past_60_month_perf = [d.close[0] / d.close[-60] for d in self.datas]

        # Calculate 6-month momentum
        six_month_momentum = [d.close[0] / d.close[-6] for d in self.datas]

        # Sort countries by 60-month performance and create late-stage groups
        sorted_indices = sorted(range(len(past_60_month_perf)), key=lambda k: past_60_month_perf[k])
        lw_group = sorted_indices[:len(self.datas) // 4]
        ll_group = sorted_indices[-len(self.datas) // 4:]

        # Rank countries in each subgroup by 6-month momentum
        lw_ranked = sorted(lw_group, key=lambda k: six_month_momentum[k], reverse=True)
        ll_ranked = sorted(ll_group, key=lambda k: six_month_momentum[k], reverse=True)

        # Set target positions
        for i, data in enumerate(self.datas):
            target_weight = 0

            # Set long positions for top 50% of best 6-month momentum in LL group
            if i in ll_ranked[:len(ll_group) // 2]:
                target_weight = 1 / (len(ll_group) // 2)

            # Set short positions for bottom 50% of worst 6-month momentum in LW group
            if i in lw_ranked[-len(lw_group) // 2:]:
                target_weight = -1 / (len(lw_group) // 2)

            # Rebalance the portfolio
            self.order_target_percent(data, target_weight)

cerebro = bt.Cerebro()
# Add data feeds and other configurations
cerebro.addstrategy(EmergingMarketStrategy)
# Run the backtest
results = cerebro.run()
```

Remember to add your data feeds and set up a Cerebro instance to execute this strategy in Backtrader. The code provided above assumes that you have already prepared the data feeds for the 26 emerging market countries.