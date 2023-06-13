<div align="center">
  <h1>ETF Arbitrage: Intraday Evidence</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1709599)

## Trading rules

- Utilize two ETFs: SPY (NYSE) and IUSA (Swiss Stock Exchange)
- Trade only when both exchanges are open
- Identify arbitrage opportunity:
    - If bid SPY / ask IUSA ≥ 1.002 or
    - If bid IUSA / ask SPY ≥ 1.002
- Initiate arbitrage opening trade:
    - Short overvalued ETF
    - Buy undervalued ETF
- Hold positions until IUSA and SPY prices converge:
    - IUSA bid (or ask) converges with SPY ask (or bid)
- Close trade upon price convergence
- Average of 40 trades per year

## Statistics

- **Markets Traded:** ETFs
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2004-2010
- **Annual Return:** 28.91%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.7
- **Annual Standard Deviation:** 14.69%

## Python code

### Backtrader

```python
import backtrader as bt

class ETF_Arbitrage_Strategy(bt.Strategy):
    def __init__(self):
        self.spy = self.datas[0]
        self.iusa = self.datas[1]
        self.order = None
        self.arbitrage_opened = False

    def next(self):
        if self.order:
            return

        spy_bid = self.spy.bid[0]
        spy_ask = self.spy.ask[0]
        iusa_bid = self.iusa.bid[0]
        iusa_ask = self.iusa.ask[0]

        if not self.arbitrage_opened:
            if spy_bid / iusa_ask >= 1.002 or iusa_bid / spy_ask >= 1.002:
                if spy_bid / iusa_ask >= 1.002:
                    self.sell(data=self.spy, size=1)
                    self.buy(data=self.iusa, size=1)
                else:
                    self.sell(data=self.iusa, size=1)
                    self.buy(data=self.spy, size=1)
                self.arbitrage_opened = True
        else:
            if abs(iusa_bid - spy_ask) < 0.001 or abs(spy_bid - iusa_ask) < 0.001:
                self.close(data=self.spy)
                self.close(data=self.iusa)
                self.arbitrage_opened = False

cerebro = bt.Cerebro()
cerebro.addstrategy(ETF_Arbitrage_Strategy)

spy_data = bt.feeds.GenericCSVData(dataname='path_to_spy_data.csv',
                                   timeframe=bt.TimeFrame.Minutes,
                                   compression=1)
iusa_data = bt.feeds.GenericCSVData(dataname='path_to_iusa_data.csv',
                                    timeframe=bt.TimeFrame.Minutes,
                                    compression=1)

cerebro.adddata(spy_data)
cerebro.adddata(iusa_data)

cerebro.run()
```

Replace `'path_to_spy_data.csv'` and `'path_to_iusa_data.csv'` with the paths to your respective data files for SPY and IUSA. The data should include bid and ask prices.