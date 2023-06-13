<div align="center">
  <h1>Asynchronous ADRs: Overnight vs Intraday Returns and Trading Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2858048)

## Trading rules

- Investment universe: SPY (SPDR S&P500 ETF) and FXI (iShares China Large-Cap ETF)
- Threshold value: k% (example: k = -0.4%)
- Calculate daily spread between ADR and SPY
- Open positions when spread is less than -0.4%: long ADR, short SPY
- Holding period: 1 day (enter and close positions at market close)
- Portfolio weighting: equal weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 2005-2015
- **Annual Return:** 14%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 16.35%

## Python code

### Backtrader

```python
import backtrader as bt

class SpreadTradingStrategy(bt.Strategy):
    params = (
        ("k", -0.004),
    )

    def __init__(self):
        self.spy = self.datas[0]
        self.fxi = self.datas[1]
        self.spread = self.spy.close - self.fxi.close

    def next(self):
        if self.spread[0] < self.params.k:
            self.sell(data=self.spy)
            self.buy(data=self.fxi)
        elif self.position:
            self.close(data=self.spy)
            self.close(data=self.fxi)

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    spy_data = bt.feeds.YahooFinanceData(
        dataname="SPY",
        fromdate=YYYY-MM-DD,
        todate=YYYY-MM-DD,
    )
    fxi_data = bt.feeds.YahooFinanceData(
        dataname="FXI",
        fromdate=YYYY-MM-DD,
        todate=YYYY-MM-DD,
    )

    cerebro.adddata(spy_data)
    cerebro.adddata(fxi_data)
    cerebro.addstrategy(SpreadTradingStrategy)
    cerebro.run()
```

Replace `YYYY-MM-DD` with the desired date range for the backtest.