<div align="center">
  <h1>Percent Accruals</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1558464)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ non-financial stocks (backtest data from Compustat)
- Define percent accruals: (Net Income - Cash from Operations) / |Net Income|
- Sorting frequency: once a year (fourth month after fiscal year-end)
- Sort stocks into deciles based on percent accruals
- Long position: stocks with the lowest percent accruals
- Short position: stocks with the highest percent accruals
- Stock weighting: equal weight
- Portfolio rebalancing: yearly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1989-2008
- **Annual Return:** 11.68%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.59
- **Annual Standard Deviation:** 13.1%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class PercentAccruals(bt.Strategy):
    params = dict(
        sorting_frequency='Y',
        deciles=10,
    )

    def __init__(self):
        self.accruals = {}
        self.order_month = None

    def next(self):
        if self.order_month is None or self.data.datetime.date(0).month == self.order_month:
            self.order_month = (self.data.datetime.date(0).month + 4) % 12
            for d in self.datas:
                net_income = d.net_income[0]
                cash_from_operations = d.cash_from_operations[0]
                percent_accruals = (net_income - cash_from_operations) / abs(net_income)
                self.accruals[d] = percent_accruals

            sorted_stocks = sorted(self.accruals.items(), key=lambda x: x[1])
            long_stocks = sorted_stocks[:len(sorted_stocks) // self.params.deciles]
            short_stocks = sorted_stocks[-len(sorted_stocks) // self.params.deciles:]

            for d in self.datas:
                if d in long_stocks:
                    self.order_target_percent(d, target=1 / len(long_stocks))
                elif d in short_stocks:
                    self.order_target_percent(d, target=-1 / len(short_stocks))
                else:
                    self.order_target_percent(d, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PercentAccruals)

    # Load and add data for each stock in the investment universe
    stocks_data = ['stock1.csv', 'stock2.csv', ...]  # Replace with actual stock data file paths

    for stock_data_file in stocks_data:
        data = pd.read_csv(stock_data_file, parse_dates=True, index_col=0)
        data_feed = bt.feeds.PandasData(dataname=data,
                                        datetime='Date',
                                        open='Open',
                                        high='High',
                                        low='Low',
                                        close='Close',
                                        volume='Volume',
                                        openinterest=None,
                                        net_income='Net Income',
                                        cash_from_operations='Cash from Operations')
        cerebro.adddata(data_feed)

    cerebro.broker.setcash(100000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)
    cerebro.run()
```