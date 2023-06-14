<div align="center">
  <h1>Mutual Fund Investor Learning and the Economic Cost of Seeking Alpha</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3160271)

## Trading rules

- Select equity funds from the CRSP Mutual Fund database
- Filter for no-load funds (eliminate entrance fees)
- Sort mutual funds by their past 6-month returns
- Divide funds into deciles
- Invest in the top decile of mutual funds (equally weighted)
- Hold funds for three months
- Alternative sorting options: fund’s proximity to 1-year high in NAV and momentum factor loading
- Combined predictor may yield better results than 6-month momentum alone

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1973-2004
- **Annual Return:** 19%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.77
- **Annual Standard Deviation:** 19.5%

## Python code

### Backtrader

```python
import backtrader as bt

class FundMomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 126),
        ('hold_period', 63),
        ('top_decile', 0.1),
    )

    def __init__(self):
        self.fund_returns = {}
        for d in self.datas:
            self.fund_returns[d._name] = d.close / d.close(-self.params.momentum_period) - 1

    def next(self):
        if self.datetime.date(0).month % 3 != 0:  # Rebalance every three months
            return

        selected_funds = sorted(
            self.datas,
            key=lambda d: self.fund_returns[d._name][0],
            reverse=True
        )[:int(len(self.datas) * self.params.top_decile)]

        target_weight = 1 / len(selected_funds)

        # Liquidate positions not in the top decile
        for d in self.datas:
            if self.getposition(d).size and d not in selected_funds:
                self.close(data=d)

        # Invest in the top decile funds
        for fund in selected_funds:
            self.order_target_percent(data=fund, target=target_weight)

# Backtrader Cerebro setup and data loading would be done here
# Make sure to filter for no-load funds and load the CRSP Mutual Fund database
```