<div align="center">
  <h1>Post Loss/Profit Announcement Drift</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1510321)

## Trading rules

- Investment universe: All NYSE, AMEX, and NASDAQ stocks (excluding stocks below $1)
- Calculate Standardized Unexpected Earnings (SUE): (Actual earnings - Expected earnings) / Earnings standard deviation
- Expected earnings derived from last 12 quarters’ earnings
- Divide stocks into deciles based on SUE
- Go long on top decile stocks (greatest positive surprise)
- Short bottom decile stocks
- Holding period: 60-180 days (investor’s choice)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1976-2005
- **Annual Return:** 26%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 4.4
- **Annual Standard Deviation:** 5%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class SUEStrategy(bt.Strategy):
    params = (
        ('holding_period', 60),
    )

    def __init__(self):
        self.sue_data = dict()
        self.long_stocks = []
        self.short_stocks = []
        self.holding_days = 0

    def next(self):
        if self.data.datetime.date(0).month != self.data.datetime.date(-1).month:
            self.rank_stocks()
            self.adjust_positions()

        self.holding_days += 1
        if self.holding_days >= self.params.holding_period:
            self.holding_days = 0
            self.nextstart()

    def rank_stocks(self):
        self.sue_data.clear()
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            if data.close[0] > 1:
                last_12_quarters_earnings = ...  # Get last 12 quarters' earnings
                expected_earnings = np.mean(last_12_quarters_earnings)
                earnings_std = np.std(last_12_quarters_earnings)
                actual_earnings = ...  # Get actual earnings
                sue = (actual_earnings - expected_earnings) / earnings_std
                self.sue_data[d] = sue

        sorted_sue = sorted(self.sue_data.items(), key=lambda x: x[1], reverse=True)
        decile = len(sorted_sue) // 10
        self.long_stocks = [x[0] for x in sorted_sue[:decile]]
        self.short_stocks = [x[0] for x in sorted_sue[-decile:]]

    def adjust_positions(self):
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            position = self.getpositionbyname(d)

            if d in self.long_stocks and not position:
                size = self.broker.getvalue() / len(self.long_stocks) / data.close[0]
                self.buy(data=data, size=size)
            elif d not in self.long_stocks and position:
                self.close(data=data)

            if d in self.short_stocks and not position:
                size = self.broker.getvalue() / len(self.short_stocks) / data.close[0]
                self.sell(data=data, size=size)
            elif d not in self.short_stocks and position:
                self.close(data=data)

    def nextstart(self):
        self.next()

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add stocks data feeds to cerebro
    # ...

    cerebro.addstrategy(SUEStrategy, holding_period=180)
    cerebro.broker.setcash(100000)
    cerebro.run()
```

Note: This code is a template and requires proper implementation of data fetching for earnings and stock prices. Additionally, make sure to add the appropriate data feeds for each stock to the cerebro instance.