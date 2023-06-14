<div align="center">
  <h1>Intraday Market-Wide Ups/Downs and Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3131369)

## Trading rules

- Investment universe: Stocks with share codes 10 or 11 in CRSP, listed on NYSE, AMEX, or NASDAQ
- Compute intraday Up/Down signal (UDS) for stocks: Number of stocks moving up minus number of stocks moving down (since last day’s close), divided by the total number of stocks
- Determine UDS at day t and time m (9:45 am)
- If UDS is positive at 9:45 am, buy the market portfolio (e.g., S&P500 index via futures, ETF, or CFD) and hold until market close
- If UDS is negative at 9:45 am, sell the market portfolio and hold until market close
- Rebalance strategy daily

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2012-2015
- **Annual Return:** 23.75%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.63
- **Annual Standard Deviation:** 31.56%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class IntradayUpDownSignal(bt.Strategy):
    params = (('time', '09:45'),)

    def __init__(self):
        self.market_portfolio = self.datas[0]  # Assuming the first data feed is the market portfolio (e.g., S&P500 index)

    def next(self):
        current_time = self.datetime.time()
        target_time = datetime.datetime.strptime(self.params.time, '%H:%M').time()

        if current_time == target_time:
            up_down_signal = 0
            total_stocks = 0

            for stock in self.datas[1:]:
                total_stocks += 1
                today_open = stock.open[0]
                yesterday_close = stock.close[-1]

                if today_open > yesterday_close:
                    up_down_signal += 1
                elif today_open < yesterday_close:
                    up_down_signal -= 1

            up_down_signal = up_down_signal / total_stocks

            if up_down_signal > 0:
                self.order_target_percent(self.market_portfolio, target=1)
            elif up_down_signal < 0:
                self.order_target_percent(self.market_portfolio, target=-1)

        elif current_time > target_time:
            self.order_target_percent(self.market_portfolio, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add the market portfolio data feed (e.g., S&P500 index) and individual stock data feeds to cerebro here
    # ...

    cerebro.addstrategy(IntradayUpDownSignal)
    cerebro.run()
```

This code defines a Backtrader strategy called `IntradayUpDownSignal` and implements the trading rules. Remember to add the market portfolio data feed and the individual stock data feeds to the `cerebro` instance before running the backtest.