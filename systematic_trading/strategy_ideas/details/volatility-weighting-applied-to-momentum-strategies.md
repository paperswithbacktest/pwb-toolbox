<div align="center">
  <h1>Volatility Weighting Applied to Momentum Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2599635)

## Trading rules

- Investment universe: 49 industry portfolios (easily replicated by ETFs)
- Monthly sorting: Portfolios divided into six groups based on cumulative past returns
    - PG1 (losers): Bottom 1/6 of ETFs with lowest cumulative returns
    - PG6 (winners): Top 1/6 of ETFs with highest cumulative returns
- Investment: Buy ETFs from PG6 group
- ETF weighting: Based on expected volatility (calculated from previous month’s realized daily volatility)
- Rebalancing: Monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1927-2014
- **Annual Return:** 25.64%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.67
- **Annual Standard Deviation:** 32.15%

## Python code

### Backtrader

```python
import backtrader as bt
import math

class IndustryMomentum(bt.Strategy):
    def __init__(self):
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def next(self):
        if self.order:
            return

        for i, d in enumerate(self.datas):
            if len(d) < 2:
                return

        # Sort ETFs based on cumulative past returns
        etfs_sorted = sorted(
            self.datas,
            key=lambda d: d.close[0] / d.close[-1] - 1,
            reverse=True
        )

        # Determine the size of each group
        group_size = math.ceil(len(self.datas) / 6)

        # Select the top 1/6 ETFs
        winners = etfs_sorted[:group_size]

        # Calculate the volatility of each winner ETF
        volatilities = [
            bt.indicators.StdDev(d.close, period=21) for d in winners
        ]

        # Calculate expected volatility for each winner ETF
        expected_volatilities = [vol[-1] for vol in volatilities]

        # Calculate the total expected volatility
        total_expected_volatility = sum(expected_volatilities)

        # Calculate the portfolio weights for each winner ETF
        weights = [vol / total_expected_volatility for vol in expected_volatilities]

        # Clear existing orders
        self.cancel(self.order)

        # Rebalance the portfolio
        for i, d in enumerate(winners):
            size = self.broker.getvalue() * weights[i] // d.close[0]
            self.order_target_size(d, size)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    # Add your data feeds here
    # for data in your_datafeeds:
    #     cerebro.adddata(data)
    cerebro.broker.set_cash(100000)
    cerebro.addstrategy(IndustryMomentum)
    cerebro.run()
```

Please note that you should add your own data feeds (e.g., using Yahoo Finance or any other data source) for the 49 industry portfolios (ETFs). The provided code assumes daily data and calculates volatility using a 21-day period (roughly one month). Adjust the data feed and the volatility calculation period according to your needs.