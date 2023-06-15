<div align="center">
  <h1>The Conservative Formula: Quantitative Investing Made Easy</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152)

## Trading rules

- Sort the 1,000 largest US stocks into two groups based on their historical 36-month stock return volatility at the end of each quarter.
- Choose the group of 500 stocks with the lowest historical volatility.
- Rank the stocks in the chosen group based on their 12-1 month price momentum and total net payout yield (NPY) to shareholders, using a scale of 1-500 where 1 denotes the best stock for each rank.
- Average the momentum and NPY ranks for each stock.
- Invest in the top 100 stocks that have the highest average rank.
- Rebalance the portfolio on a quarterly basis.
- Use an equal-weighted approach for each stock in the portfolio.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1929-2016
- **Annual Return:** 15.1%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.67
- **Annual Standard Deviation:** 16.5%

## Python code

### Backtrader

```python
# import necessary libraries
import backtrader as bt
import pandas as pd

# Set up data feed
data = bt.feeds.YahooFinanceCSVData(dataname='path/to/csv',
                                    fromdate=datetime(YYYY, MM, DD),
                                    todate=datetime(YYYY, MM, DD))

# Define strategy class
class USStocks(bt.Strategy):

    def next(self):
        # Define quarter end dates
        q_end_dates = pd.date_range(start=data.fromdate, end=data.todate, freq='Q')

        # Loop through each quarter end
        for q_end in q_end_dates:

            # Get 36-month stock return volatility for each stock at the end of the quarter
            vol_36mth = self.datas[0].pct_change(periods=36).rolling(window=36).std()

            # Split stocks into two groups based on volatility
            group_1 = vol_36mth[vol_36mth > vol_36mth.median()].index
            group_2 = vol_36mth[vol_36mth <= vol_36mth.median()].index

            # Choose group with the lowest historical volatility
            chosen_group = group_1 if vol_36mth.loc[q_end][group_1].mean() < vol_36mth.loc[q_end][group_2].mean() else group_2

            # Get 12-1 month price momentum and total net payout yield (NPY) for stocks in chosen group
            mom_12_1 = self.datas[0].pct_change(periods=12)/self.datas[0].pct_change(periods=1)
            NPY = self.datas[0].N / (self.datas[0].N + self.datas[0].D)

            # Rank stocks based on momentum and NPY, and take the average rank
            ranks = (mom_12_1.rank(ascending=False, method='dense').loc[q_end][chosen_group]
                     + NPY.rank(ascending=False, method='dense').loc[q_end][chosen_group])/2

            # Invest in the top 100 stocks with the highest average rank
            self.order_target_percent(target=0.01,
                                       data=self.datas[0],
                                       size=100,
                                       rank=ranks.loc[ranks.rank(ascending=False, method='dense') <= 100])

    def rebalance(self, target_pct_dict):
        # Rebalance the portfolio on a quarterly basis using equal-weighted approach
        self.rebalance_day = pd.date_range(start=data.fromdate, end=data.todate, freq='Q')
        if self.datas[0].datetime.date(0) in self.rebalance_day:
            target_pct = 1.0 / len(self.rebalance_day)
            for data in self.datas:
                self.order_target_percent(target=target_pct, data=data)

# Set up backtesting engine
cerebro = bt.Cerebro()

# Add the strategy to the engine
cerebro.addstrategy(USStocks)

# Add the data to the engine
cerebro.adddata(data)

# Set initial capital
cerebro.broker.setcash(1000000)

# Set commission
cerebro.broker.setcommission(commission=0.001)

# Run the backtest
cerebro.run()
```