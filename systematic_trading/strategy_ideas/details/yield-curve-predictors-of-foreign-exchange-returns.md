<div align="center">
  <h1>Yield Curve Predictors of Foreign Exchange Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1542342)

## Trading rules

- Investment universe: G10 currencies
- Monthly strategy:
    - Long on top 3 currencies with highest one-month change in 10-year yields
    - Short on bottom 3 currencies with lowest one-month change in 10-year yields
- Execution:
    - Trade currencies on spot market
    - Invest/borrow cash at one-month interbank rate (or use derivatives, like futures)
- Collateral:
    - Invested in USD at 1-month Libor rates
- Currency gains:
    - Measured against USD
- Portfolio rebalancing:
    - Conducted monthly

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1975-2009
- **Annual Return:** 5.92%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.52
- **Annual Standard Deviation:** 3.67%

## Python code

### Backtrader

```python
import backtrader as bt

class G10CurrencyStrategy(bt.Strategy):
    params = dict(
        top_currencies=3,
        bottom_currencies=3
    )

    def __init__(self):
        self.yields = {}
        for data in self.datas:
            self.yields[data._name] = data.close

    def next(self):
        if len(self.data) < 31:
            return

        change_10yr_yields = [
            (data, (self.yields[data._name][0] - self.yields[data._name][-30]) / self.yields[data._name][-30])
            for data in self.datas
        ]
        change_10yr_yields.sort(key=lambda x: x[1], reverse=True)

        long_currencies = [currency[0] for currency in change_10yr_yields[:self.params.top_currencies]]
        short_currencies = [currency[0] for currency in change_10yr_yields[-self.params.bottom_currencies:]]

        for data in self.datas:
            if data in long_currencies:
                self.order_target_percent(data, target=1.0 / len(long_currencies))
            elif data in short_currencies:
                self.order_target_percent(data, target=-1.0 / len(short_currencies))
            else:
                self.order_target_percent(data, target=0)

cerebro = bt.Cerebro()

# Load G10 currency data and add to cerebro
# ...

cerebro.addstrategy(G10CurrencyStrategy)
cerebro.run()
```

Please note that this code assumes that the G10 currency data is loaded into Backtrader. You’ll need to obtain historical price data for G10 currencies and their respective one-month interbank rates, as well as 10-year bond yields, and add them to the cerebro instance before running the strategy.