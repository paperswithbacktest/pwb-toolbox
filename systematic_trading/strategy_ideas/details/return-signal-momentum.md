<div align="center">
  <h1>Return Signal Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2971444)

## Trading rules

- Investment universe: 55 highly liquid global exchange traded futures instruments
- Calculate monthly returns for each instrument
- Use 12-month look-back period for return signs
- Determine probability of positive return signs
- Set threshold value at 0.4 for buy signal
    - Enter long position if probability >= threshold
    - Enter short position if probability < threshold
- Apply annualized ex ante volatility method for return scaling
    - Use 40% critical value for annual volatility
- Rebalance portfolio monthly

## Statistics

- **Markets Traded:** Equities, bonds, commodities, currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1985-2015
- **Annual Return:** 11.9%
- **Maximum Drawdown:** -19.5%
- **Sharpe Ratio:** 0.97
- **Annual Standard Deviation:** 12.3%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class MonthlySignPredictability(bt.Strategy):
    params = (
        ('lookback_period', 12),
        ('threshold', 0.4),
        ('vol_target', 0.4),
    )

    def __init__(self):
        self.instruments_returns = {}
        self.probabilities = {}
        self.previous_month = None

    def next(self):
        current_month = self.datetime.date(0).month

        if self.previous_month != current_month:
            for d in self.getdatanames():
                data = self.getdatabyname(d)

                if len(data) < self.params.lookback_period:
                    continue

                # Calculate monthly returns
                returns = np.log(data.close / data.close(-1))

                # Calculate probability of positive return signs
                positive_signs = (returns[-self.params.lookback_period:] > 0).sum()
                probability = positive_signs / self.params.lookback_period

                # Enter positions based on probability threshold
                if probability >= self.params.threshold:
                    self.order_target_percent(data, self.params.vol_target)
                else:
                    self.order_target_percent(data, -self.params.vol_target)

            self.previous_month = current_month

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add 55 highly liquid global exchange traded futures instruments
    # For each instrument, use the following code to add data feed
    # data = bt.feeds.GenericCSVData(dataname='path/to/your/csv', timeframe=bt.TimeFrame.Months)
    # cerebro.adddata(data)

    cerebro.addstrategy(MonthlySignPredictability)
    cerebro.run()
```

Make sure to replace `'path/to/your/csv'` with the path to the CSV file containing the historical data for each of the 55 highly liquid global exchange traded futures instruments.