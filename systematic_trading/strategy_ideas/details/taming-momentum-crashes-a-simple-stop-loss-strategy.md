<div align="center">
  <h1>Taming Momentum Crashes: A Simple Stop-Loss Strategy</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199)

## Trading rules

- Investment universe: NYSE/AMEX/NASDAQ firms (excluding CEFs, REITs, ADRs, foreign stocks, stocks under $5, and those from the lowest size decile)
- Monthly stock sorting: Based on past 6-month cumulative return (with one skip month), sort stocks into deciles
- Selection: Invest in top-performing decile, using a value-weighted approach
- Stop-loss: Set a 5% stop loss for each stock in the portfolio
- Sell rule: If stop-loss is breached, sell the stock and hold cash for the remainder of the month
- Rebalancing: Rebalance the portfolio and reset stop losses on a monthly basis

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1926-2011
- **Annual Return:** 15.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.66
- **Annual Standard Deviation:** 17.94%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.feeds as btfeeds

class MomentumStrategy(bt.Strategy):
    params = (
        ("momentum_period", 6),
        ("skip_month", 1),
        ("rebalance_freq", "monthly"),
        ("stop_loss", 0.05),
        ("value_weighted", True),
    )

    def __init__(self):
        self.rank_data = {}

    def next(self):
        if self._rebalance_required():
            self._rebalance_portfolio()

    def _rebalance_required(self):
        if self.params.rebalance_freq == "monthly":
            return self.datetime.date(ago=0).month != self.datetime.date(ago=1).month
        # Add additional logic for other rebalance frequencies if needed

    def _rebalance_portfolio(self):
        self.rank_data = self._get_ranked_data()
        self._sell_stocks()
        self._buy_stocks()

    def _get_ranked_data(self):
        momentum_period = self.params.momentum_period + self.params.skip_month
        data = {}
        for d in self.datas:
            if len(d) > momentum_period:
                past_return = d.close[0] / d.close[-momentum_period] - 1
                data[d] = past_return
        return sorted(data.items(), key=lambda x: x[1], reverse=True)

    def _sell_stocks(self):
        for i, d in enumerate(self.rank_data):
            if self.getposition(data=d[0]).size > 0 and d[0].close[0] < (1 - self.params.stop_loss) * self.getposition(data=d[0]).price:
                self.sell(data=d[0])

    def _buy_stocks(self):
        top_decile = int(len(self.rank_data) * 0.1)
        for i, d in enumerate(self.rank_data[:top_decile]):
            if self.getposition(data=d[0]).size == 0:
                if self.params.value_weighted:
                    weight = d[0].close[0] / sum(data[0].close[0] for data in self.rank_data[:top_decile])
                else:
                    weight = 1 / top_decile
                size = int(self.broker.getvalue() * weight / d[0].close[0])
                self.buy(data=d[0], size=size)

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Data loading and preprocessing
    # Replace the data_path and data_file with your actual data file path
    data_path = "./data/"
    data_file = "your_data_file.csv"

    # Add data feeds
    data = btfeeds.GenericCSVData(
        dataname=data_path + data_file,
        dtformat=("%Y-%m-%d"),
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        reverse=False
    )
    cerebro.adddata(data)

    # Add strategy to Cerebro
    cerebro.addstrategy(MomentumStrategy)

    # Set initial capital
    cerebro.broker.setcash(100000.0)

    # Run Cerebro engine
    cerebro.run()
```