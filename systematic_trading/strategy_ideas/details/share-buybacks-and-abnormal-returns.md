<div align="center">
  <h1>Share Buybacks and Abnormal Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2664098)

## Trading rules

- Investment universe: NYSE, Nasdaq, and AMEX stocks with market cap > $200 million and share price > $5
- Create daily equal-weighted portfolio of companies with buyback announcements in the past 3 months
- Hedge portfolio by shorting IWM (iShares Russell 2000 ETF)
- Calculate portfolio-level Beta using a rolling window of the most recent 250 days

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1998-2014
- **Annual Return:** 9.66%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.34
- **Annual Standard Deviation:** 7.21%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class BuybackStrategy(bt.Strategy):
    def __init__(self):
        self.iwm = self.datasymbols('IWM')  # iShares Russell 2000 ETF
        self.beta_period = 250

    def prenext(self):
        self.next()

    def next(self):
        # Investment universe: NYSE, Nasdaq, and AMEX stocks with market cap > $200 million and share price > $5
        selected_stocks = [d for d in self.datas if d.market_cap > 200e6 and d.close[0] > 5]
        # Create daily equal-weighted portfolio of companies with buyback announcements in the past 3 months
        buyback_stocks = [d for d in selected_stocks if d.buyback_announcement_date >= (self.datetime.date() - datetime.timedelta(days=90))]
        weight = 1.0 / len(buyback_stocks)
        # Buy selected stocks and hedge by shorting IWM
        for d in self.datas:
            if d in buyback_stocks:
                self.order_target_percent(d, target=weight)
            elif d == self.iwm:
                # Calculate portfolio-level Beta using a rolling window of the most recent 250 days
                beta = sum([bt.indicators.Beta(d, self.iwm, period=self.beta_period) for d in buyback_stocks]) / len(buyback_stocks)
                self.order_target_percent(d, target=-beta)
            else:
                self.order_target_percent(d, target=0.0)

cerebro = bt.Cerebro()
cerebro.addstrategy(BuybackStrategy)
# Add data feeds for stocks and IWM ETF
# ...
cerebro.run()
```

Please note that this code is just a starting point and may need further adjustments depending on your data sources and specific requirements. You will need to add data feeds for the stocks and IWM ETF, and set up initial cash, commission, etc. before running the strategy.