<div align="center">
  <h1>The Timing of Option Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2909163)

## Trading rules

- Invest in the most liquid S&P 500 index options
- Exclude illiquid securities with a price below 0.1 USD on the previous trading day
- Choose only the most traded 25% of front-month put options
- Classify options as ATM, ITM, or OTM
- Go short on a front-month OTM put option one week before maturity
- Hold the option until the expiration date (1 week)
- Maintain an equally weighted option portfolio.

## Statistics

- **Markets Traded:** Options
- **Period of Rebalancing:** Daily
- **Backtest period:** 1996-2015
- **Annual Return:** 8.69
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 2.79
- **Annual Standard Deviation:** 3.11

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class OptionsStrategy(bt.Strategy):

    params = (
        ('short_period', 5),  # Go short one week before expiry
        ('volume_percentile', 75),
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.liquid_options = []  # Store the most liquid options

    def next(self):
        if len(self.data) < self.p.short_period:
            return

        # Exclude illiquid options
        self.liquid_options = [option for option in self.datas if option.close[0] > 0.1]

        # Select the most traded 25% of front-month put options
        volume_threshold = np.percentile([option.volume[0] for option in self.liquid_options], self.p.volume_percentile)
        self.liquid_options = [option for option in self.liquid_options if option.volume[0] > volume_threshold]

        # Classify options as ATM, ITM, or OTM
        atms, itms, otms = [], [], []
        for option in self.liquid_options:
            if option.strike[0] == self.data_close[0]:  # Here you need to have the strike price data
                atms.append(option)
            elif option.strike[0] < self.data_close[0]:
                itms.append(option)
            else:
                otms.append(option)

        # Go short on a front-month OTM put option one week before maturity
        short_options = [option for option in otms if option.expiry[0] <= self.p.short_period]  # Here you need the expiry date data

        if not short_options:
            return

        # Maintain an equally weighted option portfolio
        for data in self.getpositions():
            if data not in short_options:
                self.close(data)

        weight = 1.0 / len(short_options)
        for option in short_options:
            self.sell(option, size=weight)

```