<div align="center">
  <h1>Trading Volume and Momentum: The International Evidence</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2693055)

## Trading rules

- Investment universe: NYSE and AMEX stocks (excluding REITs, ADRs, CEFs, and foreign companies)
- Sort stocks into deciles monthly based on past 12-month returns
- Define trading volume as average daily turnover percentage (daily shares traded / shares outstanding)
- Divide each momentum decile into terciles using volume
- Go long on highest volume stocks in top momentum decile; short highest volume stocks in bottom decile (equal weighting)
- Hold long-short portfolio for 3 months, then rebalance
- Purchase 1/3 of portfolio every month for 3 months; rebalance 1/3 of portfolio monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1965-1995
- **Annual Return:** 26%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.22
- **Annual Standard Deviation:** 18%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class MomentumVolumeStrategy(bt.Strategy):
    def __init__(self):
        self.order_dict = {}
        self.rebalance_dates = None

    def next(self):
        if self.datetime.date(0) in self.rebalance_dates:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        self.cancel_all_orders()
        stocks = self.get_universe_stocks()
        momentum_deciles = self.sort_by_momentum(stocks)
        volume_terciles = self.sort_by_volume(momentum_deciles)
        long_stocks = volume_terciles['top']['high']
        short_stocks = volume_terciles['bottom']['high']
        long_weight = 1.0 / len(long_stocks)
        short_weight = -1.0 / len(short_stocks)

        for stock in long_stocks:
            self.order_target_percent(stock, target=long_weight)

        for stock in short_stocks:
            self.order_target_percent(stock, target=short_weight)

    def get_universe_stocks(self):
        # Replace this function with your stock universe filtering logic
        pass

    def sort_by_momentum(self, stocks):
        # Calculate past 12-month returns for all stocks
        momentum = {stock: stock.close[0] / stock.close[-252] - 1 for stock in stocks}

        # Sort stocks into deciles based on momentum
        deciles = pd.Series(momentum).quantile([i / 10 for i in range(1, 10)]).to_dict()
        decile_groups = {k: [] for k in range(1, 11)}

        for stock, value in momentum.items():
            for i, (lower, upper) in enumerate(zip([0] + list(deciles.values()), deciles.values())):
                if lower <= value < upper:
                    decile_groups[i + 1].append(stock)
                    break

        return decile_groups

    def sort_by_volume(self, deciles):
        volume_terciles = {k: {'low': [], 'medium': [], 'high': []} for k in ['top', 'bottom']}

        for key, tercile in [('top', deciles[10]), ('bottom', deciles[1])]:
            volumes = {stock: stock.volume[0] / stock.outstanding_shares for stock in tercile}
            tercile_values = pd.Series(volumes).quantile([1 / 3, 2 / 3]).to_dict()

            for stock, value in volumes.items():
                if value < tercile_values[1 / 3]:
                    volume_terciles[key]['low'].append(stock)
                elif value < tercile_values[2 / 3]:
                    volume_terciles[key]['medium'].append(stock)
                else:
                    volume_terciles[key]['high'].append(stock)

        return volume_terciles

    def cancel_all_orders(self):
        for order in self.order_dict.values():
            self.cancel(order)
        self.order_dict.clear()

    def order_target_percent(self, stock, target):
        self.order_dict[stock] = super().order_target_percent(stock, target)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MomentumVolumeStrategy)

    # Add your data feeds and other cerebro configurations here
    # ...

    results = cerebro.run()
```

Please note that you will need to implement your own logic for filtering the stock universe in the `get_universe_stocks` method, and configure the data feeds and other cerebro settings before running the backtest.