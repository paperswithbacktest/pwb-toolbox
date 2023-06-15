<div align="center">
  <h1>When Two Anomalies Meet: The Post-Earnings Announcement Drift and the Value-Glamour Anomaly</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2601173)

## Trading rules

- Investment universe includes stocks from NYSE, AMEX, and NASDAQ.
- EAR is calculated as equally-weighted size-adjusted abnormal returns in a 3-day window centered on the earnings announcement date.
- Earnings surprises are calculated as the difference between the actual and expected EPS divided by the absolute value of the expected EPS.
- Sales-growth is the average of the annual growth in sales over the previous three years.
- At the end of June, stocks are sorted into quintiles based on Sales-growth.
- Every quarter, each stock is allocated into six sub-samples based on the signs of earnings surprise and EAR.
- The strategy takes a long position in value stocks when both earnings surprises and EARs are positive, and takes a short position in growth stocks when both earnings surprises and EARs are negative.
- Positions start from the second day after the current quarter’s earnings announcement day and end on the 2nd day before the next quarter’s earnings announcement.
- The portfolio is rebalanced quarterly.
- Stocks in the portfolio are weighted equally.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1984-2008
- **Annual Return:** 16.61%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.15
- **Annual Standard Deviation:** 11%

## Python code

### Backtrader

```python
# Import necessary modules import backtrader as bt import pandas as pd

# Define strategy

class TradingStrategy(bt.Strategy):

    def start(self):

        # Define Investment Universe
        self.universe = ['NYSE', 'AMEX', 'NASDAQ']

    def next(self):

        # Calculate EAR
        EAR = (self.data.close - self.data.close.rolling(3).mean()) / self.data.close.std()

        # Calculate Earnings Surprises
        actual_eps = self.data.eps_act
        expected_eps = self.data.eps_est
        eps_surprise = (actual_eps - expected_eps) / pd.np.abs(expected_eps)

        # Calculate Sales Growth
        sales_growth = self.data.sales.pct_change(periods=252).rolling(3).mean()

        # Sort stocks into quintiles based on Sales-growth at the end of June
        if self.datetime.date().month == 6 and self.datetime.date().day == 30:
            self.rank_sales_growth = self.data.sales_growth.rank(pct=True)

        # Allocate each stock into six sub-samples based on signs of earnings surprise and EAR
        if self.datetime.date().month in [3, 6, 9, 12] and self.datetime.date().day == 2:
            self.rank_earnings_surprise = pd.cut(eps_surprise, [-pd.np.inf, -0.5, 0, pd.np.inf], labels=[-1, 0, 1], include_lowest=True)
            self.rank_EAR = pd.qcut(EAR, 6, labels=[-3, -2, -1, 1, 2, 3])
            self.subsample = self.rank_earnings_surprise.astype(str) + self.rank_EAR.astype(str)

        # Take long positions in value stocks and short positions in growth stocks
        if self.datetime.date().month in [3, 6, 9, 12] and self.datetime.date().day > 2 and self.datetime.date().day < 2+offset:
            value_stocks = self.subsample[self.subsample == '11'].index.tolist()
            growth_stocks = self.subsample[self.subsample == '-1-1'].index.tolist()
            self.rebalance(self.equal_weight(value_stocks, growth_stocks))

    def equal_weight(self, value_stocks, growth_stocks):

        # Calculate equal weights for stocks in each quintile
        weight = 0.2 / len(value_stocks + growth_stocks)
        weights = {value_stock: weight for value_stock in value_stocks}
        weights.update({growth_stock: -weight for growth_stock in growth_stocks})
        return weights

    def rebalance(self, weights):

        # Rebalance portfolio according to weights
        for stock in self.getdatanames():
            self.order_target_percent(stock, weights.get(stock, 0))

    def stop(self):

        # Print final portfolio value
        self.log('Final portfolio value: %.2f' % self.broker.getvalue())

# Define data
data = bt.feeds.YahooFinanceData(
    dataname='AAPL',
    fromdate=datetime(2010, 1, 1),
    todate=datetime(2020, 12, 31))

# Initialize Backtrader Cerebro engine
cerebro = bt.Cerebro()

# Add data to cerebro engine
cerebro.adddata(data)

# Add trading strategy to cerebro engine
cerebro.addstrategy(TradingStrategy)

# Set cash for backtest
cerebro.broker.setcash(1000000)

# Set commission and slippage
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.set_slippage_fixed(0.10)

# Set position size
cerebro.addsizer(bt.sizers.PercentSizer, percents=99)

# Set quarterly rebalancing
cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Quarterly)
cerebro.addanalyzer(bt.analyzers.PositionsValue, _name='mypositions')
cerebro.addobserver(bt.observers.Value)

# Run backtest
cerebro.run()

# Print results
print(f"Quarterly Returns: {cerebro.analyzers.timereturn.get_analysis()['cumulative']}")
```