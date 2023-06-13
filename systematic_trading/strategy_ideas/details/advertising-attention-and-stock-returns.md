<div align="center">
  <h1>Advertising, Attention, and Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1340605)

## Trading rules

- Investment universe: NYSE, Amex, and Nasdaq firms with market capitalization > $20 million (prior year)
- Define years: t (advertising year), t-1 (prior to advertising year), t+1 (subsequent to advertising year)
- Measure ∆Advt: Change in log values of advertising expenditures from year t-1 to year t
- Rank stocks: Sort into ten deciles based on ∆Advt annually
- Zero-investment portfolio: Short decile 10 (high advertising stocks), long decile 1 (low advertising stocks)
- Purchase timing: Buy stocks in 7th month of year t+1 (ensuring all previous year financial data is available)
- Holding period: Maintain positions for 6 months
- Portfolio weighting: Equally weight stocks in the portfolio

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1996-2005
- **Annual Return:** 9.4%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.69
- **Annual Standard Deviation:** 3.2%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd

class AdvertisingEffect(bt.Strategy):
    params = (
        ('market_cap_threshold', 20e6),
        ('deciles', 10),
        ('hold_period', 6),
    )

    def __init__(self):
        self.data_market_cap = self.datas[0].market_cap
        self.data_ad_exp = self.datas[0].ad_exp

    def next(self):
        # Get year and month
        cur_year = self.data.datetime.date().year
        cur_month = self.data.datetime.date().month

        # Check for 7th month of the year (t+1)
        if cur_month != 7:
            return

        # Filter stocks by market cap
        eligible_stocks = [d for d in self.datas if d.market_cap[-1] > self.p.market_cap_threshold]

        # Calculate change in advertising expenditures
        delta_advt = [(d, np.log(d.ad_exp[-1]) - np.log(d.ad_exp[-2])) for d in eligible_stocks]

        # Rank stocks into deciles
        delta_advt.sort(key=lambda x: x[1])
        decile_size = len(delta_advt) // self.p.deciles

        # Identify long and short positions
        long_positions = delta_advt[:decile_size]
        short_positions = delta_advt[-decile_size:]

        # Set up equal weights for long and short positions
        long_weight = 1.0 / len(long_positions)
        short_weight = -1.0 / len(short_positions)

        # Enter long and short positions
        for d, _ in long_positions:
            self.order_target_percent(d, target=long_weight)

        for d, _ in short_positions:
            self.order_target_percent(d, target=short_weight)

        # Close positions after holding period
        self.sell(exectype=bt.Order.Close, when=bt.timer.SESSION_END, valid=self.p.hold_period)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(AdvertisingEffect)

    # Add data feeds (NYSE, Amex, and Nasdaq firms with market_cap and ad_exp fields)
    # ...

    # Set up the backtesting environment
    cerebro.broker.setcash(1000000.0)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)

    # Run the backtest
    results = cerebro.run()
```

Please note that you will need to create or source data feeds containing the required fields (market_cap and ad_exp) for NYSE, Amex, and Nasdaq firms. Then, add them to the `cerebro` instance using the `adddata()` method in the appropriate place in the provided code.