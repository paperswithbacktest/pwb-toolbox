<div align="center">
  <h1>CEO Interviews on CNBC</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1745085)

## Trading rules

- Investment Universe: NYSE, AMEX, and Nasdaq stocks
- Daily Monitoring: Observe CNBC for CEO interviews
- Trading Action: Short companies with CEO interviews the previous day
- Position Duration: Hold short positions for 10 days
- Portfolio Weighting: Equally weighted stocks
- Hedging Strategy: Long position in S&P futures for abnormal return exposure

## Statistics

- **Markets Traded:** futures, stocks
- **Period of Rebalancing:** Daily
- **Backtest period:** 1997-2006
- **Annual Return:** 32.08%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.11
- **Annual Standard Deviation:** 13.28%

## Python code

### Backtrader

```python
import backtrader as bt

class CEOInterviewEffect(bt.Strategy):
    def __init__(self):
        self.ceo_interviews = dict()  # Dictionary to store CEO interview dates

    def next(self):
        for data in self.datas:
            if data._name in self.ceo_interviews:
                interview_date = self.ceo_interviews[data._name]
                if self.data.datetime.date() == interview_date + bt.TimeFrame.Days(1):
                    self.sell(data=data)  # Short the stock
                    self.order_target_percent(data=data, target=-1 / len(self.datas))  # Equal weight
                # Close short position after 10 days
                elif self.data.datetime.date() == interview_date + bt.TimeFrame.Days(11):
                    self.close(data=data)

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                print(f"{self.data.datetime.date()} - Long S&P Futures: {order.executed.price}")
            elif order.issell():
                print(f"{self.data.datetime.date()} - Short {order.data._name}: {order.executed.price}")

cerebro = bt.Cerebro()

# Load data for stocks in the Investment Universe and S&P Futures

# Add strategy
cerebro.addstrategy(CEOInterviewEffect)

# Run Cerebro
results = cerebro.run()

```

Please note that the `self.ceo_interviews` dictionary must be populated with the ticker symbols and their respective CEO interview dates. Additionally, the data for stocks in the investment universe and S&P futures should be added to the Cerebro instance.