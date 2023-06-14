<div align="center">
  <h1>Is There a Value Premium Among Large Stocks?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2096310)

## Trading rules

Here are the trading rules for this strategy:

- The investment universe consists of global stocks from developed markets (North America, EU, Asia-Pacific).
- Global stocks are sorted into six portfolios at the end of each month, based on market capitalization and earnings yield.
- Firm level earnings yields are created every month as the ratio of earnings per share to stock prices at the end of each month.
- Earnings per share are the average of earnings forecasts for fiscal years t, t+1 and t+2, using mean I/B/E/S forecasts as of the third Thursday of each month.
- Negative earnings forecasts and earnings yields above 100% per year are treated as missing.
- Stocks are first sorted into “big” and “small” market capitalization bins at the end of June every year based on the median NYSE market capitalization break points from Ken French’s website.
- Within each size bin, stocks are further sorted based on their earnings yields at the end of each month.
- Stocks are sorted into “low” (bottom 30%), “medium” (mid 40%), and “high” (top 30%) earnings yield portfolios within each size bin.
- Investor goes long high earnings yield big stocks and short low earnings yield big stocks.
- Portfolio is equally weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1990-2012
- **Annual Return:** 10.95%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.45
- **Annual Standard Deviation:** 15.41%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

# Define data feed for global stocks from developed markets
data = bt.feeds.YahooFinanceData(dataname='SPY,AAPL,MSFT,AMZN,GOOGL,BABA,TSM,BRK-A,JPM,V,JNJ,WMT,MA,XOM,BAC,FB,BERK-B,JPM,CVX,VZ,PFE,WFC,PG,UNH,T,XOM,HD,IBM,CSCO,DIS,NVDA,ADBE,ABT,MCD,COST,NKE,MRK,TMO,CMCSA,PEP,ABBV,NEE,GD,MDT,UPS,PM,MMM,BA,LOW,HON,AMT,DHR,MCO,CHTR,GOOG,QCOM,ADP,CVS,ORCL,FDX')

# Define earnings yield for each stock
class EarningsYield(bt.Indicator):
    lines = ('earnings_yield',)

    def __init__(self):
        # Earnings per share (EPS) are the average of earnings forecasts for fiscal years t, t+1 and t+2
        eps_t = (1/3) * self.data0.close
        eps_t_plus_1 = (1/3) * self.data0.close(-1)
        eps_t_plus_2 = (1/3) * self.data0.close(-2)

        # Mean of earnings forecasts as of the third Thursday of each month
        eps_mean = pd.concat([eps_t, eps_t_plus_1, eps_t_plus_2], axis=1).mean(axis=1)

        # Earnings yield calculation
        self.lines.earnings_yield = (eps_mean / self.data0.close) * 100

        # Negative earnings forecasts and earnings yields above 100% per year are treated as missing.
        self.lines.earnings_yield[
            (eps_mean <= 0) | ((self.lines.earnings_yield / 12) >= 1) | np.isnan(self.lines.earnings_yield)
        ] = np.nan

# Define strategy for sorting stocks into portfolios
class PortfolioStrategy(bt.Strategy):
    def __init__(self):
        self.portfolio_month = 0
        self.rebalance_day = bt.num2date(bt.date2num(self.datas[0].datetime[-1]) - 1 * bt.TimeFrame.Months)
        self.weights = {}

    def next(self):
        if self.portfolio_month != self.datas[0].datetime.date(0).month:
            self.portfolio_month = self.datas[0].datetime.date(0).month
            self.sort_universe()

    def sort_universe(self):
        df = self.datas[0].lines.earnings_yield.to_dataframe(name='earnings_yield').reset_index()

        # Big and small market capitalization bins at the end of June every year
        if (self.datas[0].datetime.date(0).month == 6) and (self.datas[0].datetime.date(0).day >= 21):
            nyse_market_cap = pd.read_csv('nyse_market_cap.csv', index_col=0)
            nyse_market_cap = nyse_market_cap.loc[nyse_market_cap.index.year == self.datas[0].datetime.date(0).year]
            nyse_market_cap = nyse_market_cap.quantile([0.5], axis=1).values[0]

            df['market_cap_rank'] = df.groupby('date')['close'].rank(pct=True)
            df['size_bin'] = np.where(df['close'] >= nyse_market_cap, 'big', 'small')
            df.sort_values(['date', 'size_bin', 'market_cap_rank', 'earnings_yield'], inplace=True)

        # Sorting stocks based on their earnings yields at the end of each month
        else:
            df['earnings_yield_rank'] = df.groupby('date')['earnings_yield'].rank(pct=True)
            df['earnings_yield_portfolios'] = pd.cut(df['earnings_yield_rank'], [0, 0.3, 0.7, 1.0], labels=['low', 'mid', 'high'])
            df['size_bin'] = np.where(df['close'] >= nyse_market_cap, 'big', 'small')

            # Unequal weighting - long high earnings yield big stocks and short low earnings yield big stocks
            weights = dict(zip(df.loc[(df['earnings_yield_portfolios'] == 'high') & (df['size_bin'] == 'big'), 'ticker'], 0.5))
            weights.update(dict(zip(df.loc[(df['earnings_yield_portfolios'] == 'low') & (df['size_bin'] == 'big'), 'ticker'], -0.5)))

            self.weights = weights
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        self.rebalance_day = bt.num2date(bt.date2num(self.datas[0].datetime[-1]) - 1 * bt.TimeFrame.Months)
        self.order_target_percent(target=self.weights)

# Define the Cerebro engine
cerebro = bt.Cerebro()

# Add the data feed
cerebro.adddata(data)

# Add the earnings yield indicator
cerebro.addindicator(EarningsYield, name='earnings_yield')

# Add the strategy
cerebro.addstrategy(PortfolioStrategy)

# Set cash and commission
cerebro.broker.setcash(100000)
cerebro.broker.setcommission(commission=0.01)

# Run the backtest
cerebro.run()

# Plot the results
cerebro.plot()
```