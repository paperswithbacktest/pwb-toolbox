<div align="center">
  <h1>Stock Return Predictability and Seasonality</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3180992)

## Trading rules

- Investment universe: CRSP value-weighted stocks (accessible via ETF, CFD, future, or index fund)
- Identify low and high CAPE months:
    - Compare September’s CAPE ratio to the median CAPE ratio over the past 36 months
    - If September’s CAPE ratio > median, it’s a high CAPE month; otherwise, low CAPE month
- Low CAPE month strategy:
    - Hold stocks from November to October of the following year
- High CAPE month strategy:
    - Hold stocks from November to April (winter months)
    - Stay in cash during summer months
- Rebalance strategy every 6 months

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1926-2016
- **Annual Return:** 12.24%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.46
- **Annual Standard Deviation:** 17.78%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class CAPEStrategy(bt.Strategy):
    params = (
        ('CAPE_period', 36),
        ('rebalance_months', 6),
    )

    def __init__(self):
        self.CAPE_data = None  # Placeholder for CAPE data

    def next(self):
        current_month = self.data.datetime.date(0).month
        current_year = self.data.datetime.date(0).year

        if current_month == 9:  # September
            CAPE_data = self.get_CAPE_data(current_year)
            median_CAPE = np.median(CAPE_data[-self.params.CAPE_period:])
            current_CAPE = CAPE_data[-1]
            high_CAPE = current_CAPE > median_CAPE

            if high_CAPE:
                self.high_CAPE = True
            else:
                self.high_CAPE = False

        if current_month == 11:  # November
            if self.high_CAPE:
                self.order_target_percent(target=1.0)
            else:
                self.order_target_percent(target=1.0)
                self.rebalance_date = self.data.datetime.date(0) + pd.DateOffset(months=self.params.rebalance_months)

        if self.high_CAPE and current_month == 4:  # April
            self.order_target_percent(target=0.0)

        if not self.high_CAPE and self.data.datetime.date(0) == self.rebalance_date:
            self.order_target_percent(target=1.0)
            self.rebalance_date = self.data.datetime.date(0) + pd.DateOffset(months=self.params.rebalance_months)

    def get_CAPE_data(self, current_year):
        # Load or calculate CAPE data
        if self.CAPE_data is None:
            # Load CAPE data for the available years
            self.CAPE_data = pd.read_csv('CAPE_data.csv', index_col=0, parse_dates=True)
        return self.CAPE_data.loc[:str(current_year)]

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(CAPEStrategy)

    data = bt.feeds.YahooFinanceData(
        dataname='^GSPC',
        fromdate=pd.Timestamp('1926-01-01'),
        todate=pd.Timestamp('2016-12-31'),
        timeframe=bt.TimeFrame.Months,
        compression=1,
    )

    cerebro.adddata(data)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
```

Please note that you will need to provide your own CAPE data in a CSV file named ‘CAPE_data.csv’ with a datetime index and a single column containing the CAPE ratios. This code assumes that the CAPE data is monthly and aligned with the CRSP value-weighted stocks data.