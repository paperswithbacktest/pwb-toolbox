<div align="center">
  <h1>Equity Premiums in the Presidential Cycle: the Midterm Election Resolution of Uncertainty</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2903067)

## Trading rules

- Invest in all stocks in the Dow Jones Industrial Average (accessible via ETF, fund, future, or other instruments)
- During pre-election years (every four years), buy stocks at the beginning of November
- Hold stocks until the end of April
- Keep investments in the cash market during other months of the election cycle
- Cash yield not included in stated performance

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1927-2015
- **Annual Return:** 11.5%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.47
- **Annual Standard Deviation:** 24.47%

## Python code

### Backtrader

```python
import backtrader as bt
from datetime import datetime

class PreElectionStrategy(bt.Strategy):
    params = (('pre_election_years', [2020, 2024, 2028]),)

    def __init__(self):
        self.dji_etf = self.datas[0]  # Assuming DJI ETF is the first data feed

    def next(self):
        current_year = self.datetime.date().year
        current_month = self.datetime.date().month

        if current_year in self.params.pre_election_years:
            if current_month == 11 and not self.position:
                self.buy(data=self.dji_etf)  # Buy at the beginning of November
            elif current_month == 5 and self.position:
                self.sell(data=self.dji_etf)  # Sell at the end of April
        elif self.position:
            self.sell(data=self.dji_etf)  # Sell if not in pre-election year

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add DJI ETF data feed
    data = bt.feeds.YahooFinanceData(dataname='DIA',
                                     fromdate=datetime(2000, 1, 1),
                                     todate=datetime(2021, 12, 31))
    cerebro.adddata(data)

    # Add the strategy
    cerebro.addstrategy(PreElectionStrategy)

    # Set initial cash
    cerebro.broker.setcash(100000.0)

    # Run the backtest
    cerebro.run()
```