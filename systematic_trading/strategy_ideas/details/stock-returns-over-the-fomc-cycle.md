<div align="center">
  <h1>Stock Returns Over the FOMC Cycle</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2687614)

## Trading rules

- Invest in stocks during FOMC cycle weeks (weeks 0, 2, 4, 6).
- Go long S&P 500 ETF, fund, future or CFD during these weeks.
- Invest in cash during remaining days.
- FOMC cycle starts day before scheduled FOMC announcement day.
- FOMC cycle resets at each of the eight times FOMC meets per year.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1994-2013
- **Annual Return:** 11.58%
- **Maximum Drawdown:** Unknown
- **Sharpe Ratio:** 0.83
- **Annual Standard Deviation:** 13.92%

## Python code

### Backtrader

```python
import backtrader as bt

class FOMCStrategy(bt.Strategy):
    def __init__(self):
        self.fomc_start_days = [1, 15]  # 1 day before FOMC announcement day
        self.fomc_cycle_weeks = [0, 2, 4, 6]
        self.fomc_cycle_starts = [0, 2, 4, 6]  # starts on the first week of the year

        self.long_signal = False

    def is_fomc_cycle(self, date):
        fomc_date = self.get_fomc_date(date)
        fomc_week = fomc_date.isocalendar()[1] % 2

        if fomc_week in self.fomc_cycle_weeks:
            if fomc_week in self.fomc_cycle_starts:
                self.long_signal = True
            return True

        self.long_signal = False
        return False

    def get_fomc_date(self, date):
        fomc_year = date.year
        fomc_month = [1, 3, 4, 6, 7, 9, 10, 12][(date.month - 1) // 2]
        fomc_day = self.fomc_start_days[date.month % 2]
        return datetime(fomc_year, fomc_month, fomc_day)

    def next(self):
        if self.is_fomc_cycle(self.data.datetime.date(0)):
            if not self.position:
                self.order_target_percent(target=1.0)
        else:
            if self.position:
                self.close()
```