<div align="center">
  <h1>Double-Sort Trading Strategy on Commodity Futures: Performance Evaluation and Stop-Loss Implementation</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2614241)

## Trading rules

- Calculate monthly roll-returns for each commodity future
- Split futures contracts into three portfolios: Low, Mid, and High
- Sort High portfolio commodities into two sub-portfolios: High-Winner and High-Loser, based on past month’s mean return
    - High-Winner: highest roll-returns and best past performance
- Sort Low portfolio commodities into two sub-portfolios: Low-Winner and Low-Loser, based on past month’s mean return
    - Low-Loser: lowest roll-returns and worst past performance
- Buy High-Winner portfolio and short Low-Loser portfolio
- Maintain position for one month

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1979-2004
- **Annual Return:** 21.8%
- **Maximum Drawdown:** -44.7%
- **Sharpe Ratio:** 0.79
- **Annual Standard Deviation:** 27.6%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class CommodityStrategy(bt.Strategy):
    params = (
        ("lookback", 30),
    )

    def __init__(self):
        self.data_names = []
        for d in self.datas:
            self.data_names.append(d._name)
        self.returns = {d._name: [] for d in self.datas}

    def next(self):
        if len(self) % self.params.lookback != 0:
            return

        for data in self.datas:
            roll_return = (data.close[0] - data.close[-self.params.lookback]) / data.close[-self.params.lookback]
            self.returns[data._name].append(roll_return)

        if len(self.returns[self.data_names[0]]) < 2:
            return

        past_month_returns = {key: value[-1] for key, value in self.returns.items()}
        sorted_returns = sorted(past_month_returns.items(), key=lambda x: x[1])
        n = len(sorted_returns) // 3
        low_portfolio = sorted_returns[:n]
        high_portfolio = sorted_returns[-n:]
        low_loser = [d[0] for d in low_portfolio if d[1] < 0]
        high_winner = [d[0] for d in high_portfolio if d[1] > 0]

        for data in self.datas:
            if data._name in high_winner:
                self.buy(data=data)
            elif data._name in low_loser:
                self.sell(data=data)

        self.returns = {key: value[-1:] for key, value in self.returns.items()}

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Load commodity futures data and add them to the Cerebro
    for symbol in ['<commodity1>', '<commodity2>', '<commodity3>', ...]:
        data = bt.feeds.GenericCSVData(
            dataname=f'<data_path>/{symbol}.csv',
            dtformat='%Y-%m-%d',
            openinterest=-1,
            nullvalue=0.0,
            plot=False,
            name=symbol
        )
        cerebro.adddata(data)

    cerebro.addstrategy(CommodityStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=10)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Replace `<commodity1>`, `<commodity2>`, `<commodity3>`, and so on with the actual commodity names, and replace `<data_path>` with the path to the folder containing the CSV files for each commodity future. The CSV files should have columns for the date, open, high, low, close, and volume, with the date in the format `YYYY-MM-DD`.