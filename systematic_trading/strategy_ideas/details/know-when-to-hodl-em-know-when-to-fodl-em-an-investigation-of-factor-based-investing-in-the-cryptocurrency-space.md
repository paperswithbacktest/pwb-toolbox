<div align="center">
  <h1>‘Know When to Hodl ’Em, Know When to Fodl ’Em’: An Investigation of Factor Based Investing in the Cryptocurrency Space</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3055498)

## Trading rules

- Investment universe: 11 cryptocurrencies
- Construct equally-weighted benchmark with 10% exposure
- Rebalance benchmark at each rebalancing date
- Create equally-weighted factor composite portfolios (momentum, value, carry)
- Combine factor portfolios with benchmark for enhanced portfolios
- Address negative weights by setting currency weight to zero
- Rebalance portfolio weekly

## Statistics

- **Markets Traded:** Cryptos
- **Period of Rebalancing:** Weekly
- **Backtest period:** 2013-2017
- **Annual Return:** 38.3%
- **Maximum Drawdown:** None
- **Sharpe Ratio:** 2.9
- **Annual Standard Deviation:** 13.2%

## Python code

### Backtrader

```python
import backtrader as bt

class CryptoStrategy(bt.Strategy):
    def __init__(self):
        self.momentum = bt.indicators.Momentum(self.data.close)
        self.value = bt.indicators.Value(self.data.close)
        self.carry = bt.indicators.Carry(self.data.close)

    def next(self):
        num_cryptos = 11
        equal_weight = 1 / num_cryptos

        # Construct equally-weighted benchmark with 10% exposure
        benchmark_weight = equal_weight * 0.1

        # Rebalance benchmark at each rebalancing date
        for i, d in enumerate(self.datas):
            self.order_target_percent(d, target=benchmark_weight)

        # Create equally-weighted factor composite portfolios (momentum, value, carry)
        factor_portfolios = [self.momentum, self.value, self.carry]

        for factor in factor_portfolios:
            weights = [equal_weight if factor[i] > 0 else 0 for i in range(num_cryptos)]

            # Combine factor portfolios with benchmark for enhanced portfolios
            enhanced_weights = [benchmark_weight + w for w in weights]

            # Address negative weights by setting currency weight to zero
            adjusted_weights = [w if w > 0 else 0 for w in enhanced_weights]

            # Rebalance portfolio weekly
            self.rebalance(adjusted_weights)

    def rebalance(self, weights):
        for i, d in enumerate(self.datas):
            self.order_target_percent(d, target=weights[i])

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add cryptocurrency data feeds
    for i in range(11):
        data = bt.feeds.PandasData(dataname=my_crypto_data[i])
        cerebro.adddata(data)

    cerebro.addstrategy(CryptoStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)

    # Set the rebalance frequency to weekly
    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Weeks)

    results = cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Note: This code assumes you have data for 11 cryptocurrencies in a list named `my_crypto_data`. You will need to replace it with your actual data. Also, you need to implement the `Value` and `Carry` indicators for the strategy as they are not part of Backtrader’s built-in indicators.