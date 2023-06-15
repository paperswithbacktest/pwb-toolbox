<div align="center">
  <h1>Short-Term Momentum and Reversals in Large Stocks</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2029984)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ stocks priced above $5/share
- Monthly filtering: Larger stocks selected based on size median
- Calculate realized returns and annualized volatilities for each stock over past six months
- Exclude one week (seven calendar days) before each month to minimize microstructure biases
- Sort stocks into quintiles based on past returns and volatility
- Go long on highest-performing quintile stocks with highest volatility
- Go short on lowest-performing quintile stocks with highest volatility
- Equal-weight stocks within portfolio
- Hold positions for six months, rebalancing 1/6 of the portfolio monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1964-2009
- **Annual Return:** 16.46%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.65
- **Annual Standard Deviation:** 19.22%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class MomentumReversalVolatilityStrategy(bt.Strategy):
    def __init__(self):
        self.stock_data = {}
        self.filtered_stocks = []
        self.position_period = 6
        self.rebalance_dates = []

    def prenext(self):
        self.next()

    def next(self):
        if len(self.data) > self.position_period * 30:
            return

        if self.data.datetime.date(ago=0) in self.rebalance_dates:
            self.update_filtered_stocks()
            self.update_positions()

    def update_filtered_stocks(self):
        stocks_data = []
        for d in self.datas:
            if d.close[0] > 5:
                stocks_data.append({
                    'data': d,
                    'market_cap': d.close[0] * d.volume[0],
                })

        median_market_cap = np.median([stock['market_cap'] for stock in stocks_data])
        self.filtered_stocks = [stock for stock in stocks_data if stock['market_cap'] >= median_market_cap]

    def update_positions(self):
        for stock in self.filtered_stocks:
            stock_data = stock['data']
            past_returns = np.log(stock_data.close.get(size=6 * 30)) - np.log(stock_data.close.get(size=6 * 30, ago=30))
            past_volatility = np.std(past_returns) * np.sqrt(252)
            stock.update({
                'returns': past_returns[-1],
                'volatility': past_volatility
            })

        self.filtered_stocks.sort(key=lambda x: (-x['volatility'], -x['returns']))
        quintile_size = len(self.filtered_stocks) // 5
        long_stocks = self.filtered_stocks[:quintile_size]
        short_stocks = self.filtered_stocks[-quintile_size:]

        for stock in long_stocks + short_stocks:
            data = stock['data']
            target_weight = 1 / quintile_size
            if stock in long_stocks:
                self.order_target_percent(data, target_weight)
            elif stock in short_stocks:
                self.order_target_percent(data, -target_weight)

cerebro = bt.Cerebro()
cerebro.broker.setcash(1000000)
cerebro.broker.setcommission(commission=0.001)

# Add stock data to cerebro
# ...

cerebro.addstrategy(MomentumReversalVolatilityStrategy)

# Run backtest
results = cerebro.run()

# Plot results
cerebro.plot()
```

Note that you will need to add the stock data to the cerebro object before running the backtest. This code snippet assumes that you have the stock data from NYSE, AMEX, and NASDAQ already prepared.