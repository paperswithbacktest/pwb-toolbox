<div align="center">
  <h1>Profitable Mean Reversion after Large Price Drops: A Story of Day and Night in the S&P 500, 400 Mid Cap and 600 Small Cap Indices</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2272795)

## Trading rules

- S&P 500 Index stocks as investment universe
- Buy 50 worst performing stocks from open-to-close (first decile)
- Purchase shares at market close
- Hold shares overnight
- Sell at next day’s market open
- Equal weight for all stocks in portfolio

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2000-2010
- **Annual Return:** 57.7%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 3.03
- **Annual Standard Deviation:** 17.7%

## Python code

### Backtrader

```python
import backtrader as bt

class HalfDayReversal(bt.Strategy):
    params = (
        ('num_stocks', 50),
    )

    def __init__(self):
        self.rank = {}

    def next(self):
        # Get today's open and close prices for all stocks
        opens = [data.open[0] for data in self.datas]
        closes = [data.close[0] for data in self.datas]

        # Calculate open-to-close returns
        returns = [(closes[i] - opens[i]) / opens[i] for i in range(len(opens))]

        # Rank stocks by returns
        self.rank = sorted(zip(self.datas, returns), key=lambda x: x[1])

        # Sell all stocks at today's open
        for data in self.datas:
            if self.getposition(data).size > 0:
                self.sell(data=data, exectype=bt.Order.Market)

        # Buy the num_stocks worst-performing stocks at today's close
        for data, _ in self.rank[:self.params.num_stocks]:
            cash = self.broker.get_cash() / self.params.num_stocks
            size = cash // data.close[0]
            self.buy(data=data, size=size, exectype=bt.Order.Market, valid=bt.Order.DAY)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add S&P 500 Index stocks data feeds here
    # cerebro.adddata(data_feed)

    cerebro.addstrategy(HalfDayReversal)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Note: Please make sure to add the S&P 500 Index stocks data feeds in the appropriate section in the code. This code is for educational purposes only and may require adjustments according to the specific data and broker API used.