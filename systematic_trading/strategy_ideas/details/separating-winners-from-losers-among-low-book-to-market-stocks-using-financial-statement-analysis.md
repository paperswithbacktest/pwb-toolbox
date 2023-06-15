<div align="center">
  <h1>Separating Winners from Losers Among Low Book-to-Market Stocks Using Financial Statement Analysis</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=403180)

## Trading rules

- Investment universe: Non-financial firms listed on NYSE and AMEX (excluding foreign companies, closed-end funds, REITs, ADRs, and firms with a price below $1 or negative book-to-market ratio)
- Focus on top quintile firms with highest book-to-market ratio
- Triple sort process:
    1. Select top quintile stocks with highest 12-month momentum (winner portfolio) and bottom quintile stocks with lowest 12-month momentum (loser portfolio)
    2. Calculate BOS ratio for each portfolio (covariance between 12-month return and average volume)
    3. Choose stocks with lowest BOS ratio from winner portfolio and highest BOS ratio from loser portfolio
- Calculate GSCORE for each stock in winner and loser portfolios
- Go long on top quintile stocks with highest GSCORE ratio from winner portfolio
- Go short on bottom quintile stocks with lowest GSCORE ratio from loser portfolio
- Rebalance monthly with equal-weighted stocks

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1982-2008
- **Annual Return:** 47.64%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.55
- **Annual Standard Deviation:** 79%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from scipy.stats import mstats

class TripleSortStrategy(bt.Strategy):
    def __init__(self):
        self.stock_data = dict()

    def prenext(self):
        self.next()

    def next(self):
        if self.datetime.date(0).month != self.datetime.date(-1).month:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        eligible_stocks = self.get_eligible_stocks()
        top_quintile_bm = eligible_stocks.quantile(0.8)['book_to_market']
        high_bm_stocks = eligible_stocks[eligible_stocks['book_to_market'] > top_quintile_bm]
        sorted_momentum = high_bm_stocks.sort_values('momentum_12m', ascending=False)
        winner_port, loser_port = self.get_winner_loser_portfolios(sorted_momentum)
        winner_port = self.update_bos_ratio(winner_port)
        loser_port = self.update_bos_ratio(loser_port, asc=False)
        self.adjust_positions(winner_port, loser_port)

    def get_eligible_stocks(self):
        # Add logic to filter eligible stocks based on your data
        pass

    def get_winner_loser_portfolios(self, sorted_momentum):
        quintile = len(sorted_momentum) // 5
        winner_port = sorted_momentum.head(quintile)
        loser_port = sorted_momentum.tail(quintile)
        return winner_port, loser_port

    def update_bos_ratio(self, df, asc=True):
        df['bos_ratio'] = df['momentum_12m'].rolling(12).cov(df['average_volume'])
        return df.sort_values('bos_ratio', ascending=asc)

    def adjust_positions(self, winner_port, loser_port):
        for data in self.getdatas():
            symbol = data._name
            position = self.getposition(data).size
            if symbol in winner_port.index:
                target_size = self.broker.getvalue() / len(winner_port)
                self.order_target_value(data, target_size)
            elif symbol in loser_port.index:
                target_size = -self.broker.getvalue() / len(loser_port)
                self.order_target_value(data, target_size)
            elif position:
                self.close(data)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY: {order.data._name}, PRICE: {order.executed.price}')
            elif order.issell():
                self.log(f'SELL: {order.data._name}, PRICE: {order.executed.price}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.data._name}')

    def log(self, txt, dt=None):
        dt = dt or self.datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

cerebro = bt.Cerebro()
# Add your data feeds
# cerebro.adddata(...)
cerebro.addstrategy(TripleSortStrategy)
cerebro.broker.setcash(100000.0)
cerebro.run()
```

Please note that this code is a template and you’ll need to adjust it according to your specific data structure and source. Additionally, the GSCORE calculation is not included as it requires specific data and calculations based on the referenced paper or trading system.