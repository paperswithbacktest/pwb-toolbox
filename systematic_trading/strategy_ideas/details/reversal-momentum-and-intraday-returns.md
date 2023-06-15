<div align="center">
  <h1>Reversal, Momentum and Intraday Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2991183)

## Trading rules

- Begin with domestic, primary stocks on NYSE, AMEX, and Nasdaq
- Exclude stocks priced below $5 or in the smallest NYSE size decile
- Sort stocks into small, mid, and large groups based on 9 NYSE size deciles
- Focus on the “large” subsample
- Calculate intraday returns using TAQ database trading prices (P1: last price before 14:00, P2: last price before 16:00)
- Intraday return: (P2 / P1) - 1
- Accumulate intraday returns over one-month period
- Sort stocks into deciles based on prior monthly returns (accumulated intraday returns)
- Buy losers (bottom decile) and sell winners (top decile)
- Rebalance portfolio monthly with equal weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1993-2014
- **Annual Return:** 5.12%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.56
- **Annual Standard Deviation:** 9.21%

## Python code

### Backtrader

Here’s a sample implementation of the trading rules using Backtrader in Python:

```python
import backtrader as bt
import pandas as pd

class IntradayReversal(bt.Strategy):
    def __init__(self):
        self.intraday_returns = {}

    def next(self):
        if self.data.datetime.date(ago=0) != self.data.datetime.date(ago=-1):
            self.rank_stocks()

        for data in self.datas:
            if data._name in self.losers:
                self.order_target_percent(data, target=1.0 / len(self.losers))
            elif data._name in self.winners:
                self.order_target_percent(data, target=-1.0 / len(self.winners))
            else:
                self.order_target_percent(data, target=0)

    def rank_stocks(self):
        self.winners, self.losers = [], []

        for data in self.datas:
            symbol = data._name
            p1, p2 = data.close[0], data.close[-1]
            intraday_return = (p2 / p1) - 1

            if symbol in self.intraday_returns:
                self.intraday_returns[symbol].append(intraday_return)
            else:
                self.intraday_returns[symbol] = [intraday_return]

            if len(self.intraday_returns[symbol]) == 20:
                self.intraday_returns[symbol].pop(0)

        sorted_stocks = sorted(self.intraday_returns.items(), key=lambda x: sum(x[1]))
        self.losers = [stock[0] for stock in sorted_stocks[:10]]
        self.winners = [stock[0] for stock in sorted_stocks[-10:]]

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(IntradayReversal)

    # Load your custom data here (use NYSE, AMEX, and Nasdaq stocks with price > $5 and in the large subsample)
    # For example:
    # data = bt.feeds.PandasData(dataname=pd.read_csv('your_data.csv', index_col=0, parse_dates=True))
    # cerebro.adddata(data)

    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=99)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Please note that this is just a sample implementation and you will need to adjust it based on your specific requirements and data sources.