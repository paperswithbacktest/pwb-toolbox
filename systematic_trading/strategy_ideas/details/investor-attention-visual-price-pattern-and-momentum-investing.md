<div align="center">
  <h1>Investor Attention, Visual Price Pattern, and Momentum Investing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2292895)

## Trading rules

- Investment universe: All stocks on NYSE, AMEX, and NASDAQ
- Calculate acceleration ratio: 6-month momentum - (6-month momentum six months prior)
- Sort stocks into deciles, equal weight within each decile
- Long high acceleration stocks, short low acceleration stocks
- Acceleration effect materializes after 6 months, strongest returns at 12 months
- Optimal strategy: Wait 6 months after portfolio formation to buy stocks, hold for 6 months
- Combine acceleration effect with momentum effect:
    - Compute acceleration as: (momentum T-7 to T-12) - (momentum T-13 to T-18)
    - Sort stocks into deciles based on acceleration
    - At end of month T, go long on strongest momentum stocks (T-1 to T-6) from top acceleration portfolio
    - Short weakest momentum stocks (T-1 to T-6) from bottom acceleration portfolio
    - Hold long/short portfolio for six months

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1926-2003
- **Annual Return:** 18.24%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.48
- **Annual Standard Deviation:** 29.7%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class AccelerationMomentum(bt.Strategy):
    def __init__(self):
        self.stock_data = dict()

    def prenext(self):
        self.next()

    def next(self):
        # Every 6 months, reevaluate the portfolio
        if self.datetime.month % 6 == 0 and self.datetime.day == 1:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        stocks_accel = []
        for d in self.datas:
            # Calculate 6-month momentum
            momentum_6m = d.close[0] / d.close[-126]
            # Calculate 6-month momentum six months prior
            momentum_6m_prior = d.close[-126] / d.close[-252]
            # Calculate acceleration ratio
            acceleration_ratio = momentum_6m - momentum_6m_prior
            stocks_accel.append((d, acceleration_ratio))

        # Sort stocks by acceleration ratio and divide into deciles
        sorted_stocks = sorted(stocks_accel, key=lambda x: x[1], reverse=True)
        deciles = np.array_split(sorted_stocks, 10)

        # Get top and bottom deciles
        top_decile = deciles[0]
        bottom_decile = deciles[-1]

        # Sort top decile by momentum (T-1 to T-6)
        top_decile_momentum = sorted(top_decile, key=lambda x: x[0].close[0] / x[0].close[-6], reverse=True)

        # Sort bottom decile by momentum (T-1 to T-6)
        bottom_decile_momentum = sorted(bottom_decile, key=lambda x: x[0].close[0] / x[0].close[-6])

        # Go long on top decile stocks
        for stock in top_decile_momentum:
            self.order_target_percent(stock[0], target=1.0 / len(top_decile_momentum))

        # Go short on bottom decile stocks
        for stock in bottom_decile_momentum:
            self.order_target_percent(stock[0], target=-1.0 / len(bottom_decile_momentum))

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add all stocks in the investment universe
    # (Replace 'stock_data' with actual stock data)
    for stock in stock_data:
        data = bt.feeds.PandasData(dataname=stock_data[stock])
        cerebro.adddata(data)

    cerebro.addstrategy(AccelerationMomentum)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
```

Note: This code is a starting point and should be adapted according to your specific data source and requirements. The ‘stock_data’ variable should be replaced with actual stock data from NYSE, AMEX, and NASDAQ. Additionally, ensure that your stock data has the required history for the calculations.