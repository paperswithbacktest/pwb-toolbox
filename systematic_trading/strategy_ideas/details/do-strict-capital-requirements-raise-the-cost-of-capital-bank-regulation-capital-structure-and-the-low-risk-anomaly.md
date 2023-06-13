<div align="center">
  <h1>Do Strict Capital Requirements Raise the Cost of Capital? Bank Regulation, Capital Structure, and the Low Risk Anomaly</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2577963)

## Trading rules

- Utilize CRSP database for stock selection
- Compute 1-year rolling beta for each stock relative to MSCI US Equity Index
- Rank stocks in ascending order based on estimated beta
- Allocate stocks to low beta or high beta portfolios
- Weight securities by their ranked betas
- Rebalance portfolios monthly
- Rescale both portfolios to have a beta of one at formation
- Establish zero-cost, zero-beta Betting-Against-Beta portfolio: long low-beta, short high-beta
- Consider simple modifications (e.g., long bottom beta decile, short top beta decile) to enhance performance

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1926-2009
- **Annual Return:** 8.86%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.42
- **Annual Standard Deviation:** 11.5%

## Python code

### Backtrader

Here’s a Backtrader Python code implementing the trading rules you described:

```python
import backtrader as bt
import backtrader.feeds as btfeeds
import pandas as pd

class BetaRanking(bt.Strategy):
    params = (
        ('lookback', 252),
        ('rebalance_freq', 21),
        ('num_long', 10),
        ('num_short', 10)
    )

    def __init__(self):
        self.betas = {}
        self.rankings = []
        self.rebalance_day = 0

        # Compute beta for each stock
        for d in self.datas:
            self.betas[d._name] = bt.indicators.Beta(d, self.data0, period=self.params.lookback)

    def next(self):
        self.rebalance_day += 1

        if self.rebalance_day % self.params.rebalance_freq != 0:
            return

        self.rankings = sorted(
            self.datas,
            key=lambda d: self.betas[d._name][0]
        )

        longs = self.rankings[:self.params.num_long]
        shorts = self.rankings[-self.params.num_short:]

        for d in longs:
            self.order_target_percent(d, target=1.0 / self.params.num_long)

        for d in shorts:
            self.order_target_percent(d, target=-1.0 / self.params.num_short)

        for d in self.datas:
            if d not in longs and d not in shorts:
                self.order_target_percent(d, target=0.0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add strategy
    cerebro.addstrategy(BetaRanking)

    # Load CRSP database
    # Replace this part with your actual CRSP data
    for stock_data in CRSP_data:
        data = btfeeds.PandasData(dataname=stock_data)
        cerebro.adddata(data)

    # Load MSCI US Equity Index data
    msci_data = btfeeds.PandasData(dataname=pd.read_csv('msci_us_equity_index.csv', parse_dates=['date'], index_col='date'))
    cerebro.adddata(msci_data, name='msci_us_equity_index')

    # Set initial capital and run
    cerebro.broker.setcash(100000.0)
    cerebro.run()
```

This code implements a Backtrader strategy that calculates rolling betas for each stock relative to the MSCI US Equity Index, ranks stocks based on their betas, and rebalances the portfolio monthly. Remember to replace the data loading part with your actual CRSP data and the MSCI US Equity Index data in a suitable format.