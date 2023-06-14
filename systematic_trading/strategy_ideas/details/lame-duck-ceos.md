<div align="center">
  <h1>Lame-Duck CEOs</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3193048)

## Trading rules

- Investment universe: S&P 1500 firms
- Portfolio: Protracted Succession portfolio
    - Includes firms with a lame duck CEO reign (incumbent CEO departure announced, new CEO identity unknown)
    - Firms added to portfolio at the beginning of the month following the incumbent CEO’s departure announcement
    - Firms remain in the portfolio until the end of the month when the new CEO identity is revealed
- Portfolio weighting: Equally weighted
- Rebalancing: Monthly
- Hedging: Against Carhart’s 4 factors (market, value, size, and momentum)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2005-2014
- **Annual Return:** 11.35%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.5
- **Annual Standard Deviation:** 14.71%

## Python code

### Backtrader

```python
import backtrader as bt

class ProtractedSuccessionStrategy(bt.Strategy):
    params = (
        ('investment_universe', None),
        ('protracted_succession_data', None),
        ('rebalance_period', 21),
        ('hedging_factors', None),
    )

    def __init__(self):
        self.inds = {}
        for d in self.getdatanames():
            self.inds[d] = {}
            self.inds[d]['carhart_factors'] = bt.indicators.SimpleMovingAverage(
                self.getdatabyname(d).close, period=self.params.hedging_factors
            )

    def next(self):
        if self.datetime.date(0).day != 1:
            return

        lame_duck_ceos = self.params.protracted_succession_data.get_lame_duck_ceos(
            self.datetime.date(0)
        )

        if not lame_duck_ceos:
            return

        target_weights = 1.0 / len(lame_duck_ceos)

        for d in self.getdatanames():
            if d in lame_duck_ceos:
                self.order_target_percent(data=self.getdatabyname(d), target=target_weights)
            else:
                self.order_target_percent(data=self.getdatabyname(d), target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add investment universe data
    investment_universe_data = [...]  # Get S&P 1500 firms data

    for data in investment_universe_data:
        cerebro.adddata(data)

    # Add protracted succession data
    protracted_succession_data = [...]  # Get protracted succession data

    # Add Carhart's 4 factors data
    carhart_factors_data = [...]  # Get Carhart's 4 factors data

    for data in carhart_factors_data:
        cerebro.adddata(data, name=data._name)

    cerebro.addstrategy(
        ProtractedSuccessionStrategy,
        investment_universe=investment_universe_data,
        protracted_succession_data=protracted_succession_data,
        hedging_factors=carhart_factors_data
    )

    results = cerebro.run()
```