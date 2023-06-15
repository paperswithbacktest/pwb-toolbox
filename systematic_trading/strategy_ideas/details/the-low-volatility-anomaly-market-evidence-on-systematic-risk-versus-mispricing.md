<div align="center">
  <h1>The Low-Volatility Anomaly: Market Evidence on Systematic Risk versus Mispricing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1739227)

## Trading rules

- Investment universe: Global or US large-cap stocks
- Monthly portfolio construction
- Rank stocks based on past 3-year volatility of weekly returns
- Create equally weighted decile portfolios
- Go long on top decile stocks (lowest volatility)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1986-2006
- **Annual Return:** 11.3%
- **Maximum Drawdown:** 10.1%
- **Sharpe Ratio:** 0.72
- **Annual Standard Deviation:** 0%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class LowVolatilityStrategy(bt.Strategy):
    params = (
        ('lookback', 36 * 4),  # 3 years of weekly lookback
    )

    def __init__(self):
        self.volatility = {}

    def next(self):
        # Monthly portfolio construction
        if len(self.data) % 4 != 0:
            return

        # Calculate past 3-year volatility for all stocks
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            returns = np.diff(np.log(data.get(size=self.p.lookback)))
            self.volatility[d] = np.std(returns)

        # Sort stocks based on volatility
        sorted_stocks = sorted(self.volatility, key=self.volatility.get)

        # Calculate position size
        position_size = 1.0 / (len(sorted_stocks) // 10)

        # Create equally weighted decile portfolios
        decile = len(sorted_stocks) // 10
        top_decile_stocks = sorted_stocks[:decile]

        # Go long on top decile stocks (lowest volatility)
        for d in self.getdatanames():
            data = self.getdatabyname(d)
            if d in top_decile_stocks:
                self.order_target_percent(data, target=position_size)
            else:
                self.order_target_percent(data, target=0.0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for global or US large-cap stocks
    # ...

    # Add the strategy
    cerebro.addstrategy(LowVolatilityStrategy)

    # Run the strategy
    cerebro.run()
```

Please note that you will need to add your data feeds for global or US large-cap stocks in the appropriate section of the code.