<div align="center">
  <h1>Cryptomarket Discounts</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3124394)

## Trading rules

- Investment universe: Currency pairs across various exchanges, focusing on Bitcoin-dollar pairs
- Compute discount D(m,j): D(m,j) = P(m,1)/P(1,1) - 1 for each market m and fiat currency j (USD in this case)
- Group assets by discounts: Rank pairs from lowest negative (highest premium) to highest positive discounts, creating 5 portfolios
- Portfolio 1: Lowest discounts (highest premium); Portfolio 5: Highest discounts
- Strategy: Using a risk-free rate and $1 initial investment
- For Portfolio 5: Buy Bitcoin in market m, sell Bitcoin for dollars on Bitfinex (market m = 1; can also use Bitcoin futures)
- Repay initial $1 borrowed plus accrued interest
- Portfolio equally weighted and rebalanced daily

## Statistics

- **Markets Traded:** Cryptocurrencies
- **Period of Rebalancing:** Daily
- **Backtest period:** 2015-2018
- **Annual Return:** 17.82%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 4.21
- **Annual Standard Deviation:** 3.28%

## Python code

### Backtrader

```python
import backtrader as bt

class CryptoArbitrageStrategy(bt.Strategy):
    def __init__(self):
        self.markets = self.datas

    def next(self):
        discounts = []
        for market in self.markets:
            discount = market.close[0] / self.markets[0].close[0] - 1
            discounts.append((market, discount))
        sorted_markets = sorted(discounts, key=lambda x: x[1])
        portfolio_size = len(sorted_markets) // 5
        portfolio_5 = sorted_markets[-portfolio_size:]
        for market, _ in portfolio_5:
            self.order_target_percent(market, target=1/portfolio_size)
        self.sell(data=self.markets[0], size=1)  # Sell on Bitfinex (market m=1)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add Bitcoin-dollar pairs from various exchanges as data feeds
    # Example: cerebro.adddata(bt.feeds.PandasData(dataname=data_frame))

    cerebro.addstrategy(CryptoArbitrageStrategy)
    cerebro.broker.setcash(1.0)  # $1 initial investment
    cerebro.run()
    cerebro.plot()
```

Please note that you’ll need to load data feeds with Bitcoin-dollar pairs from various exchanges and add them to the `cerebro` instance using `cerebro.adddata()` before running the strategy. This code snippet assumes that you have the `backtrader` library installed and available for use.