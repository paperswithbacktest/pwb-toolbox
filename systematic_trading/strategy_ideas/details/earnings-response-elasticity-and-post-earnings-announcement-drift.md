<div align="center">
  <h1>Earnings Response Elasticity and Post-Earnings-Announcement Drift</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3309788)

## Trading rules

- Investment universe: NYSE stocks
- Calculate Earnings Response Elasticity (ERE) for each stock in a quarter
    - ERE = |Abnormal Return (3-day window centered on earnings announcement date)| / Accounting Earnings Surprise
- Sort stocks into quintiles based on ERE
- Long position: Bottom ERE quintile with positive earnings surprises and positive abnormal returns
- Short position: Top ERE quintile with negative earnings surprises and negative abnormal returns
- Hold stocks until the next quarter
- Rebalance strategy daily due to varying earnings announcement dates

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1985-2008
- **Annual Return:** 8.5%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.26
- **Annual Standard Deviation:** 17.15%

## Python code

### Backtrader

```python
import backtrader as bt
import math
import numpy as np

class EREStrategy(bt.Strategy):
    params = (
        ('quintile_size', 0.2),
    )

    def __init__(self):
        self.ere = dict()
        self.next_quarter = dict()

    def next(self):
        # Calculate ERE for each stock in a quarter
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            if data.datetime.date() >= self.next_quarter[d]:
                accounting_earnings_surprise = data.close[0] - data.close[-1]
                abnormal_return = abs(data.close[0] - data.close[-1]) / data.close[-1]
                self.ere[d] = abnormal_return / accounting_earnings_surprise if accounting_earnings_surprise != 0 else 0
                self.next_quarter[d] = data.datetime.date() + bt.DateOffset(months=3)

        # Sort stocks into quintiles based on ERE
        sorted_stocks = sorted(self.ere.items(), key=lambda x: x[1])
        quintile_size = int(len(sorted_stocks) * self.params.quintile_size)

        # Enter long and short positions
        for i, (d, ere_value) in enumerate(sorted_stocks):
            data = self.getdatabyname(d)
            position = self.getpositionbyname(d)

            if i < quintile_size:
                if ere_value > 0 and data.close[0] > data.close[-1] and not position:
                    self.buy(data=data)
            elif i >= len(sorted_stocks) - quintile_size:
                if ere_value < 0 and data.close[0] < data.close[-1] and not position:
                    self.sell(data=data)

            # Close positions at the end of the quarter
            if data.datetime.date() >= self.next_quarter[d]:
                if position:
                    self.close(data=data)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data for NYSE stocks
    for ticker in nyse_stock_list:
        data = bt.feeds.YahooFinanceData(dataname=ticker, fromdate=start_date, todate=end_date)
        cerebro.adddata(data, name=ticker)

    cerebro.addstrategy(EREStrategy)
    cerebro.run()
```

Please note that this code assumes you have a list of NYSE stock tickers called `nyse_stock_list` and appropriate `start_date` and `end_date` variables. Replace them with your actual data sources and date range.