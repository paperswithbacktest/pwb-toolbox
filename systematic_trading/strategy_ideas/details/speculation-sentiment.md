<div align="center">
  <h1>Speculation Sentiment</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3063551)

## Trading rules

- Investment universe consists of all NYSE stocks.
- 6 levered ETFs are used to construct the index.
- The levered ETF pairs track specific indexes.
- J denotes the subset of long ETFs and K denotes the subset of short ETFs.
- Percent share changes are computed for each of the six ETFs comprising the index.
- The final step in forming the index is to estimate the AR(1) process.
- Time series of residuals forms the Speculation Sentiment Index.
- Monthly sensitivity to lagged SSI t+i is estimated for each stock.
- Quintiles are formed for each stock based on monthly sensitivity.
- A long-short portfolio is constructed using quintiles one and five.
- The position in the long-short portfolio depends on the previous month’s realization of SSI.
- The portfolio is scaled by the magnitude of SSI.
- When SSI is small, a fraction of the portfolio is held in cash.
- When SSI is large, the exposure of the portfolio is increased using leverage.
- The portfolio is value-weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2010-2016
- **Annual Return:** 17.98%
- **Maximum Drawdown:** Very complex strategy
- **Sharpe Ratio:** 0.76
- **Annual Standard Deviation:** 18.51%

## Python code

### Backtrader

```python
# Import necessary modules
import backtrader as bt

# Define investment universe
universe = bt.feeds.YahooFinanceData(dataname='AAPL', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))

# Define 6 levered ETFs
etf1 = bt.feeds.YahooFinanceData(dataname='ETF1', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))
etf2 = bt.feeds.YahooFinanceData(dataname='ETF2', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))
etf3 = bt.feeds.YahooFinanceData(dataname='ETF3', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))
etf4 = bt.feeds.YahooFinanceData(dataname='ETF4', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))
etf5 = bt.feeds.YahooFinanceData(dataname='ETF5', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))
etf6 = bt.feeds.YahooFinanceData(dataname='ETF6', fromdate=datetime(2000,1,1), todate=datetime(2021,12,31))

# Tracking specific indexes
etf1_track = 'Index1_name'
etf2_track = 'Index2_name'
etf3_track = 'Index3_name'
etf4_track = 'Index4_name'
etf5_track = 'Index5_name'
etf6_track = 'Index6_name'

# Subset of long ETFs and short ETFs
j = [etf1, etf3, etf5]
k = [etf2, etf4, etf6]

# Compute percent share changes of each ETF
etf1_pct = bt.indicators.PercentChange(etf1.close)
etf2_pct = bt.indicators.PercentChange(etf2.close)
etf3_pct = bt.indicators.PercentChange(etf3.close)
etf4_pct = bt.indicators.PercentChange(etf4.close)
etf5_pct = bt.indicators.PercentChange(etf5.close)
etf6_pct = bt.indicators.PercentChange(etf6.close)

# Estimating AR(1) process
ar1 = bt.indicators.ARMA(etf1_pct, p=1, q=0)

# Forming Speculation Sentiment Index
ssi = etf1_pct - ar1

# Monthly sensitivity to lagged SSI
monthly_sensitivity = bt.indicators.TimeFramePandas(sma(ssi, period=21))

# Form quintiles based on monthly sensitivity
quintiles = bt.indicators.Quintiles(monthly_sensitivity, period=1)

# Construct long-short portfolio
long_short_pf = quintiles.lines.quintile1 - quintiles.lines.quintile5

# Position depends on previous month's realization of SSI
month_lag = bt.indicators.TimeFramePandas(lag(ssi, period=1))

# Scale portfolio by magnitude of SSI
scale_by_ssi = bt.indicators.TimeFramePandas(ssi)

# When SSI is small, hold some of the portfolio in cash
cash_buffer = bt.indicators.If(scale_by_ssi < 0.5, 0.1 * long_short_pf, 0)

# When SSI is large, increase exposure to portfolio using leverage
leverage = bt.indicators.If(scale_by_ssi > 1.5, 2.0, 1.0)

# Value weight portfolio and rebalance monthly
weight = bt.indicators.MarketCap(universe.close)
rebalance = bt.algos.Rebalance(monthly=True)
```