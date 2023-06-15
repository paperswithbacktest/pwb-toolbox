<div align="center">
  <h1>Time series reversal in trend-following strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2971875)

## Trading rules

- The investment universe consists of 24 commodity futures, 9 foreign exchange futures, 9 equity indexes, and 13 government bonds from 6 developed countries.
- Monthly returns are calculated from the daily excess cumulative return series.
- Monthly SMA is used to calculate trend following signals for each individual instrument based on returns during months T-23 to T-12.
- SMAs of T-23 to T-12 period excess returns during the next 12 months (T-11 to T) are observed to check if they are positive or not.
- In the next month (T+1), futures with negative SMA signal based on calculation during months T-23 to T-12 and positive returns during months T-11 to T are picked and held. These futures are called “Fault Losers” and comprise a sub-portfolio.
- Trading signals are generated every month and position sizes are rebalanced every month.
- Annualised ex ante volatility method is used to scale returns of each asset.
- 40% critical value is used for the annual volatility.

## Statistics

- **Markets Traded:** [‘bonds’, ‘commodities’, ‘currencies’, ‘equities’]
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1985-2015
- **Annual Return:** 24.4%
- **Maximum Drawdown:** -26.2%
- **Sharpe Ratio:** 1.17
- **Annual Standard Deviation:** 20.9%

## Python code

### Backtrader

```python
# Define the investment universe
universe = ['commodity_futures_1', 'commodity_futures_2', ... 'government_bonds_13']

# Define the monthly returns
monthly_returns = daily_excess_cumulative_return_series.resample('M').last().pct_change()

# Calculate SMA for trend following signals
sma_23_12 = monthly_returns.rolling(12).mean().shift(11)

# Calculate SMAs for next 12 months
sma_11_0 = monthly_returns.shift(-1).rolling(12).mean()

# Find fault losers
fault_losers = ((sma_23_12 < 0) & (sma_11_0 > 0) & (monthly_returns > 0)).any(axis=1)

# Generate trading signals and rebalance positions
if fault_losers:
    self.buy()
else:
    self.sell()

# Scale returns using annualised ex ante volatility
volatility = monthly_returns.std() * np.sqrt(12)
scaled_returns = monthly_returns / volatility

# Apply 40% critical value
threshold = volatility * 0.4
```