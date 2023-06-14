<div align="center">
  <h1>Monetary Policy and Currency Returns: The Foresight Saga</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2983043)

## Trading rules

- Use next-month fed funds futures 3 days prior to FOMC announcement to calculate target rate change.
- Calculate fed funds futures spread over the target by finding the difference between expected target rate and the fed funds target rate.
- Long dollar against basket of developed currencies if spread is greater or equal to 12.5 bps.
- Short dollar against basket of developed currencies if spread is lower or equal to -12.5 bps.
- No action is taken if the spread is between -12.5 and 12.5 bps.
- Leverage ratio of 5 to 1 is used.
- Buy 2 days before FOMC announcement, and sell in the afternoon of the FOMC announcement day.

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Daily
- **Backtest period:** 1994-2015
- **Annual Return:** 7.17%
- **Maximum Drawdown:** Unknown
- **Sharpe Ratio:** 0.98
- **Annual Standard Deviation:** 7.28%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class FedFundsFutures(bt.Strategy):
    params = (('leverage', 5),)

    def __init__(self):
        self.fomc = self.datas[0]
        self.spread = None
        self.target_change = None

    def next(self):
        if self.fomc.datetime.date().weekday() == 2:
            self.calculate_fed_funds_futures_spread()
            if self.spread >= 12.5:
                self.buy_dollar()
            elif self.spread <= -12.5:
                self.sell_dollar()

    def calculate_fed_funds_futures_spread(self):
        end_date = self.fomc.datetime.date()
        start_date = end_date - datetime.timedelta(days=3)
        next_month = self.get_next_month(end_date.month, end_date.year)
        target_rate = self.get_target_rate(next_month)
        expected_rate = self.get_expected_rate(start_date, end_date, next_month)
        self.target_change = target_rate - self.get_previous_day_target_rate(end_date)
        self.spread = expected_rate - target_rate

    def get_next_month(self, month, year):
        if month == 12:
            return datetime.datetime(year + 1, 1, 1).date()
        else:
            return datetime.datetime(year, month + 1, 1).date()

    def get_target_rate(self, month):
        # Implement logic to get target rate for specified month
        pass

    def get_expected_rate(self, start_date, end_date, month):
        # Implement logic to get expected rate for specified month between start and end dates
        pass

    def get_previous_day_target_rate(self, date):
        # Implement logic to get target rate for the previous day
        pass

    def buy_dollar(self):
        # Implement logic to long dollar against basket of developed currencies with leverage
        pass

    def sell_dollar(self):
        # Implement logic to short dollar against basket of developed currencies with leverage
        pass

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add data feeds here

    cerebro.addstrategy(FedFundsFutures)
    cerebro.run()
```