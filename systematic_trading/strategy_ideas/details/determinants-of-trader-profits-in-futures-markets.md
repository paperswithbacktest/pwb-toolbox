<div align="center">
  <h1>Determinants of Trader Profits in Futures Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1781975)

## Trading rules

- Investment universe: 27 commodity futures (12 agricultural, 5 energy, 4 livestock, 5 metal, and lumber)
- Hold nearest contract until one month before maturity; roll to second nearest contract to avoid physical delivery
- Exclude 25% of commodities with lowest average open interest over preceding weeks from trading in the nearest week
- Hedging pressure: long positions divided by total positions of commercial traders (using Commitment of Traders report data)
- Portfolio:
    - Long positions on 20% of contracts with lowest hedging pressure (hedgers net short) over previous R weeks
    - Short positions on 20% of contracts with highest hedging pressure (hedgers net long) over previous R weeks
- Positions held for next H weeks; new long-short portfolios formed after that
- Ranking period (R) options: 4, 13, 26, and 52 weeks
- Holding period (H) options: 4, 13, 26, and 52 weeks
- Total: 16 long-short portfolios created and rebalanced

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1992-2010
- **Annual Return:** 11.4%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.41
- **Annual Standard Deviation:** 18.09%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class HedgersEffect(bt.Strategy):
    params = (
        ('ranking_period', [4, 13, 26, 52]),
        ('holding_period', [4, 13, 26, 52]),
    )

    def __init__(self):
        self.hedging_pressure = dict()

    def next(self):
        if self.datas[0].datetime.date(0).isocalendar()[1] % min(self.params.ranking_period) == 0:
            self.calculate_hedging_pressure()

        if self.datas[0].datetime.date(0).isocalendar()[1] % min(self.params.holding_period) == 0:
            self.rebalance_portfolio()

    def calculate_hedging_pressure(self):
        for data in self.datas:
            long_positions = data.positions.long
            total_positions = data.positions.total
            self.hedging_pressure[data._name] = long_positions / total_positions

    def rebalance_portfolio(self):
        sorted_hedging_pressure = sorted(self.hedging_pressure.items(), key=lambda x: x[1])
        long_symbols = [symbol for symbol, _ in sorted_hedging_pressure[:int(len(sorted_hedging_pressure) * 0.2)]]
        short_symbols = [symbol for symbol, _ in sorted_hedging_pressure[-int(len(sorted_hedging_pressure) * 0.2):]]

        for data in self.datas:
            if data._name in long_symbols:
                self.order_target_percent(data, target=1 / len(long_symbols))
            elif data._name in short_symbols:
                self.order_target_percent(data, target=-1 / len(short_symbols))
            else:
                self.order_target_percent(data, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add 27 commodity futures data feeds
    # ...

    cerebro.addstrategy(HedgersEffect)
    cerebro.run()
```

Please note that this code is a basic implementation of the strategy and assumes that you have already set up the data feeds for the 27 commodity futures. The actual implementation may require modifications based on the data source and format you are using. Additionally, you may need to add a custom commission scheme, slippage, and additional logic for rolling contracts based on your specific data.