<div align="center">
  <h1>Cross-Sectional Seasonalities in International Government Bond Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212995)

## Trading rules

- Investment universe: 22 developed and emerging markets with 10+ years bonds
- Define SAME variable: Average local currency return in the same calendar month as t for the past 20 years
- Sort bond buckets: Based on SAME each month
- Form zero-investment portfolio: Use 10% cutoff point for equal-weighted long and short positions
    - Long: Bonds with highest SAME
    - Short: Bonds with lowest SAME
- Rebalance portfolio: Monthly
- Recommendation: Use futures on the bonds for better liquidity and lower transaction costs

## Statistics

- **Markets Traded:** Bonds
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1980-2018
- **Annual Return:** 7.7%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.56
- **Annual Standard Deviation:** 13.85%

## Python code

### Backtrader

```python
import datetime
import backtrader as bt

class SAME(bt.Strategy):
    def __init__(self):
        self.bond_bucket_data = {}
        self.same = {}
        self.sorted_buckets = []
        self.rebalance_date = None

    def prenext(self):
        if len(self.data) > 240:  # 20 years * 12 months
            self.next()

    def next(self):
        if self.rebalance_date is None or self.data.datetime.date(0) >= self.rebalance_date:
            self.calculate_same()
            self.sort_buckets()
            self.rebalance_portfolio()
            self.rebalance_date = self.data.datetime.date(0) + datetime.timedelta(days=30)

    def calculate_same(self):
        for bond in self.getdatanames():
            data = self.getdatabyname(bond)
            month_t = data.datetime.date(0).month
            same_sum = 0
            same_count = 0
            for i in range(1, 241):  # 20 years * 12 months
                if data.datetime.date(-i).month == month_t:
                    same_sum += data.close[-i]
                    same_count += 1
            self.same[bond] = same_sum / same_count

    def sort_buckets(self):
        self.sorted_buckets = sorted(self.same, key=self.same.get)

    def rebalance_portfolio(self):
        cutoff = int(len(self.sorted_buckets) * 0.1)
        for i, bond in enumerate(self.sorted_buckets):
            data = self.getdatabyname(bond)
            position_size = self.broker.get_cash() * 0.1 / data.close[0]
            if i < cutoff:
                self.sell(data=data, size=position_size)
            elif i >= len(self.sorted_buckets) - cutoff:
                self.buy(data=data, size=position_size)

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Add bond data feeds here
    # For example:
    # data_feed = bt.feeds.PandasData(dataname=bond_data, name='Bond1')
    # cerebro.adddata(data_feed)

    cerebro.addstrategy(SAME)
    cerebro.broker.set_cash(100000)
    results = cerebro.run()
    cerebro.plot()
```

Please note that you need to add the bond data feeds to the code above, as indicated in the comment. This code assumes you have 20 years of monthly historical data for the 22 developed and emerging markets with 10+ years bonds. The data should include the closing prices in local currency.