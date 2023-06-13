<div align="center">
  <h1>Are Earnings Predictable? Evidence from Equity Issues and Buyback Announcements</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2589966)

## Trading rules

- Investment universe: NYSE/AMEX/Nasdaq stocks (excluding ADRs, CEFs, and REITs)
- Exclude bottom 25% of firms by market cap
- Quarterly search for companies announcing stock repurchase programs (minimum 5% of outstanding stocks) within -30 to -15 days before earnings announcement
- Go long on stocks with announced buybacks during -10 to +15 days around earnings announcement
- Equally weighted portfolio
- Daily portfolio rebalancing

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1987-2013
- **Annual Return:** 25.2%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.27
- **Annual Standard Deviation:** 11.11%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class BuybackEarningsStrategy(bt.Strategy):
    params = (
        ('buyback_days_before', 30),
        ('buyback_days_after', 15),
        ('earnings_days_before', 10),
        ('earnings_days_after', 15),
        ('min_buyback_pct', 0.05),
    )

    def __init__(self):
        self.order = None
        self.buy_date = None
        self.target_marketcap_quantile = 0.75

    def next(self):
        # Cancel existing orders
        if self.order:
            self.cancel(self.order)

        # Check if buy date is within earnings window
        if self.buy_date and self.buy_date - datetime.timedelta(days=self.p.earnings_days_before) <= self.datetime.date() <= self.buy_date + datetime.timedelta(days=self.p.earnings_days_after):
            # Check if stock is in the top 75% market cap
            marketcap_rank = self.data.marketcap.rank()
            if marketcap_rank >= self.target_marketcap_quantile * len(self.datas):
                # Calculate equal portfolio weight
                weight = 1.0 / len(self.datas)

                # Calculate position size
                position_size = self.broker.getvalue() * weight / self.data.close[0]

                # Go long
                self.order = self.buy(data=self.data, size=position_size)

        # Check for buyback announcement
        if self.data.buyback_pct[0] >= self.p.min_buyback_pct and self.data.buyback_days_before[0] <= self.p.buyback_days_before and self.data.buyback_days_after[0] >= self.p.buyback_days_after:
            self.buy_date = self.datetime.date()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, Size: %.2f, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.size,
                          order.executed.price,
                          order.executed.value,
                          order.executed.comm))
            else:
                self.log('SELL EXECUTED, Size: %.2f, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.size,
                          order.executed.price,
                          order.executed.value,
                          order.executed.comm))

        self.order = None
```