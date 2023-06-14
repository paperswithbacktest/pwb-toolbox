<div align="center">
  <h1>It Takes Two to Tango: Fundamental Timing in Stock Market</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3252887)

## Trading rules

- Annually in June, rank stocks based on one of eight accounting variables for the previous fiscal year
- Assign stocks to one of ten equal-weighted deciles
- Create spread portfolio: long position on highest average return decile (Decile High) and short position on other extreme decile (Decile Low)
- Rebalance portfolios at the end of June the following year
- Calculate 50-day (MA50) and 200-day (MA200) moving averages for each stock in portfolio monthly
- At month-end, compare MA50 (short trend) with MA200 (long trend) to filter stocks:
    - Remove stocks from Decile High if MA50 is below MA200
    - Remove stocks from Decile Low if MA50 is above MA200

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1965-2013
- **Annual Return:** 19.14%
- **Maximum Drawdown:** -4.13%
- **Sharpe Ratio:** 1.06
- **Annual Standard Deviation:** 14.31%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class AnomalyStrategy(bt.Strategy):
    params = (
        ('accounting_variables', 8),
        ('deciles', 10),
    )

    def __init__(self):
        self.ma50 = {data: bt.indicators.SimpleMovingAverage(data, period=50) for data in self.datas}
        self.ma200 = {data: bt.indicators.SimpleMovingAverage(data, period=200) for data in self.datas}

    def next(self):
        date = self.datas[0].datetime.date(0)
        month = date.month
        year = date.year

        if month == 6:
            self.rank_stocks()
            self.adjust_portfolio()

        self.filter_stocks()

    def rank_stocks(self):
        self.stock_ranks = {}

        for data in self.datas:
            self.stock_ranks[data] = self.calculate_accounting_variable_rank(data)

        self.stock_ranks = sorted(self.stock_ranks.items(), key=lambda x: x[1])

    def calculate_accounting_variable_rank(self, data):
        # Placeholder implementation
        return 0

    def adjust_portfolio(self):
        decile_size = len(self.stock_ranks) // self.params.deciles
        decile_high = self.stock_ranks[-decile_size:]
        decile_low = self.stock_ranks[:decile_size]

        self.decile_high_stocks = [stock for stock, _ in decile_high]
        self.decile_low_stocks = [stock for stock, _ in decile_low]

        for data in self.decile_high_stocks:
            self.order_target_percent(data, target=1 / len(self.decile_high_stocks))

        for data in self.decile_low_stocks:
            self.order_target_percent(data, target=-1 / len(self.decile_low_stocks))

    def filter_stocks(self):
        for data in self.decile_high_stocks:
            if self.ma50[data] < self.ma200[data]:
                self.sell(data)

        for data in self.decile_low_stocks:
            if self.ma50[data] > self.ma200[data]:
                self.buy(data)

cerebro = bt.Cerebro()

# Add stocks data to cerebro here
# ...

cerebro.addstrategy(AnomalyStrategy)
cerebro.run()
```

The provided code is a starting point for implementing the strategy in Backtrader. You will need to add your own logic for calculating the accounting variable rank and add the necessary data feeds to `cerebro`.