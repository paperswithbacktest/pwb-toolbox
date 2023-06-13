<div align="center">
  <h1>Avoiding Momentum Crashes: Dynamic Momentum and Contrarian Trading</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2942641)

## Trading rules

- Investment universe: All US stocks
- Monthly sorting: Stocks sorted into deciles based on previous-year returns, excluding most recent month
- Long position: Decile with highest returns (W – Winners)
- Short position: Decile with lowest returns (L – Losers)
- Standard strategy: WML (Winner minus Losers) portfolio held for one month
- Market crash trigger: Market move >2 standard deviations below mean return during previous month
- Contrarian strategy: Switch WML to LMW (Loser minus Winner) portfolio after market crash
- Contrarian position duration: Held for three months or until no market plunge occurs
- Rebalancing: Monthly, with value-weighted portfolio

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1927-2015
- **Annual Return:** 21.74%
- **Maximum Drawdown:** -39.39%
- **Sharpe Ratio:** 0.81
- **Annual Standard Deviation:** 26.74%

## Python code

### Backtrader

```python
import backtrader as bt

class DynamicMomentumContrarian(bt.Strategy):
    params = dict(
        lookback_period=12,  # Previous year for returns calculation
        deciles=10,  # Number of deciles for stock sorting
        crash_threshold=2,  # Number of standard deviations for market crash trigger
        contrarian_duration=3,  # Number of months to hold contrarian position
    )

    def __init__(self):
        self.returns = {}
        self.market_ret = bt.ind.PctChange(bt.ind.SP500())
        self.crash_signal = False
        self.contrarian_counter = 0

    def next(self):
        if len(self.data) <= self.p.lookback_period:
            return

        if self.contrarian_counter > 0:
            self.contrarian_counter -= 1
            if self.contrarian_counter == 0:
                self.crash_signal = False

        self.returns = {
            data: bt.ind.PctChange(data, period=self.p.lookback_period)
            for data in self.datas
        }
        sorted_stocks = sorted(self.returns, key=lambda x: self.returns[x][0])
        winners = sorted_stocks[-len(sorted_stocks) // self.p.deciles :]
        losers = sorted_stocks[: len(sorted_stocks) // self.p.deciles]

        if not self.crash_signal:
            market_mean = bt.ind.SimpleMovingAverage(self.market_ret, period=self.p.lookback_period)
            market_std_dev = bt.ind.StdDev(self.market_ret, period=self.p.lookback_period)
            if self.market_ret[0] < (market_mean[0] - self.p.crash_threshold * market_std_dev[0]):
                self.crash_signal = True
                self.contrarian_counter = self.p.contrarian_duration

        for data in self.datas:
            if self.crash_signal:
                if data in winners:
                    self.order_target_percent(data, -1 / self.p.deciles)
                elif data in losers:
                    self.order_target_percent(data, 1 / self.p.deciles)
            else:
                if data in winners:
                    self.order_target_percent(data, 1 / self.p.deciles)
                elif data in losers:
                    self.order_target_percent(data, -1 / self.p.deciles)
                else:
                    self.order_target_percent(data, 0)

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Add stocks datafeeds to cerebro

    # Add strategy to cerebro
    cerebro.addstrategy(DynamicMomentumContrarian)

    # Run backtest
    results = cerebro.run()
```

Keep in mind that this code requires the addition of the necessary datafeeds to `cerebro` and assumes you are using the S&P 500 index as a proxy for the market.