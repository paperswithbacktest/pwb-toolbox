<div align="center">
  <h1>Fundamental Strength and Short-Term Return Reversal</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3097420)

## Trading rules

- Investment universe: Common stocks listed on NYSE, AMEX, and NASDAQ (share code 10 or 11)
- Exclude stocks priced below $5 at formation period end
- FSCORE range: 0-9 points (1 point for each positive signal)
    - Positive return-on-assets (ROA)
    - Positive cash flow from operations
    - Positive change in ROA
    - Positive difference between net income and accruals
    - Decrease in long-term debt-to-total-assets ratio
    - Positive change in current ratio
    - No new common equity issuance
    - Positive change in gross margin ratio
    - Positive change in asset turnover ratio
- Construct quarterly FSCORE with latest financial statement information
- Match monthly reversal data with most recent quarterly FSCORE
- Firm classification:
    - Fundamentally strong (FSCORE 7-9)
    - Fundamentally middle (FSCORE 4-6)
    - Fundamentally weak (FSCORE 0-3)
- Identify large stocks: Top 40% by market capitalization at formation month end
- Sort stocks by past 1-month returns and latest quarterly FSCORE
- Take long position in past losers with strong fundamentals (7-9) and short position in past winners with weak fundamentals (0-3)
- Equally weighted strategy, rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1984-2015
- **Annual Return:** 12.01%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.39
- **Annual Standard Deviation:** 20.61%

## Python code

### Backtrader

Here is the Backtrader Python code for the given trading rules:

```python
import backtrader as bt

class FScoreStrategy(bt.Strategy):
    def __init__(self):
        self.price = bt.indicators.Close(self.data)
        self.market_cap = self.data.market_cap
        self.roa = self.data.return_on_assets
        self.cfo = self.data.cash_flow_operations
        self.delta_roa = self.roa - self.roa(-1)
        self.ni_accruals = self.data.net_income - self.data.accruals
        self.delta_debt_ratio = self.data.long_term_debt(-1) / self.data.total_assets(-1) - self.data.long_term_debt / self.data.total_assets
        self.delta_current_ratio = self.data.current_ratio - self.data.current_ratio(-1)
        self.new_common_equity = self.data.new_common_equity
        self.delta_gross_margin = self.data.gross_margin - self.data.gross_margin(-1)
        self.delta_asset_turnover = self.data.asset_turnover - self.data.asset_turnover(-1)

    def prenext(self):
        self.next()

    def next(self):
        if self.inds[self.data]['fscore'] is None:
            return

        long_list = []
        short_list = []

        for d in self.getdatanames():
            if self.getposition(d).size:
                self.sell(data=d)

            if self.price[d][0] < 5:
                continue

            fscore = 0
            fscore += self.roa[d][0] > 0
            fscore += self.cfo[d][0] > 0
            fscore += self.delta_roa[d][0] > 0
            fscore += self.ni_accruals[d][0] > 0
            fscore += self.delta_debt_ratio[d][0] < 0
            fscore += self.delta_current_ratio[d][0] > 0
            fscore += self.new_common_equity[d][0] == 0
            fscore += self.delta_gross_margin[d][0] > 0
            fscore += self.delta_asset_turnover[d][0] > 0

            self.inds[d]['fscore'][0] = fscore

            if fscore >= 7 and self.data1_month[d][0] < 0:
                long_list.append(d)

            if fscore <= 3 and self.data1_month[d][0] > 0:
                short_list.append(d)

        long_weight = 1.0 / len(long_list) if long_list else 0
        short_weight = 1.0 / len(short_list) if short_list else 0

        for d in long_list:
            self.buy(data=d, size=long_weight * self.broker.get_cash())

        for d in short_list:
            self.sell(data=d, size=short_weight * self.broker.get_cash())
```

Note that this code assumes that the required data, such as return on assets, cash flow from operations, and other financial ratios, have been added to the Backtrader data feed. You may need to preprocess the data or modify the code to accommodate your specific data sources.