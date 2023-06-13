<div align="center">
  <h1>Are Return Seasonalities Due to Risk or Mispricing? Evidence from Seasonal Reversals</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3276334)

## Trading rules

- Investment universe: Stocks listed on NYSE, Amex, and NASDAQ
- Exclude securities other than ordinary common shares
- Construct a seasonal reversals factor at month t
    - Sort stocks by average other-calendar-month returns (excluding month t)
    - Use last 20 years of data for formation
    - Create six portfolios
- Go long on the two low-average portfolios
- Short the two high-average portfolios
- Rebalance strategy monthly
- Use value-weighted approach

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1963-2016
- **Annual Return:** 5.54%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.19
- **Annual Standard Deviation:** 8.07%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np
from datetime import timedelta

class SeasonalReversals(bt.Strategy):
    params = (
        ("lookback", 20 * 12),
        ("portfolios", 6),
        ("long_short_ratio", 2),
    )

    def __init__(self):
        self.order_dict = {}
        self.data_dict = {data._name: data for data in self.datas}

    def next(self):
        # Get current date
        current_date = self.datas[0].datetime.date(0)

        if current_date.month != (current_date - timedelta(days=1)).month:
            self.rebalance()

    def rebalance(self):
        # Calculate seasonal reversals factor
        returns = {}
        for stock, data in self.data_dict.items():
            historical_returns = np.array([
                data.close.get(size=-month, ago=-month) / data.close.get(size=-month, ago=-month - 1) - 1
                for month in range(1, 13) if month != data.datetime.date(0).month
            ])
            avg_return = historical_returns.mean()
            returns[stock] = avg_return

        sorted_stocks = sorted(returns, key=returns.get)
        long_stocks = sorted_stocks[:self.params.long_short_ratio]
        short_stocks = sorted_stocks[-self.params.long_short_ratio:]

        # Cancel existing orders
        for orders in self.order_dict.values():
            for order in orders:
                self.cancel(order)

        # Rebalance portfolio
        for stock, data in self.data_dict.items():
            if stock in long_stocks:
                target_weight = 1.0 / (2 * self.params.long_short_ratio)
                self.order_target_percent(data, target_weight, exectype=bt.Order.Market)
            elif stock in short_stocks:
                target_weight = -1.0 / (2 * self.params.long_short_ratio)
                self.order_target_percent(data, target_weight, exectype=bt.Order.Market)
            else:
                self.order_target_percent(data, 0, exectype=bt.Order.Market)

if __name__ == "__main__":
    cerebro = bt.Cerebro()

    # Add data feeds (NYSE, Amex, NASDAQ) for the desired stocks to cerebro
    # Example:
    # data = bt.feeds.YahooFinanceData(dataname="AAPL", fromdate=datetime(2000, 1, 1), todate=datetime(2022, 1, 1))
    # cerebro.adddata(data)

    cerebro.addstrategy(SeasonalReversals)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
```