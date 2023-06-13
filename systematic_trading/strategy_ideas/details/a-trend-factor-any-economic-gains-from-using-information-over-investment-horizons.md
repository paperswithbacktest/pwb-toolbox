<div align="center">
  <h1>A Trend Factor: Any Economic Gains from Using Information over Investment Horizons?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2182667)

## Trading rules

- Investment universe includes NYSE, Amex, and Nasdaq stocks (excluding closed-end funds, REITs, unit trusts, ADRs, and foreign stocks).
- Only the largest stocks are used, sorted by market cap into five quintiles.
- Monthly trend signals are constructed using 3-, 5-, and 20-day moving averages, calculated on the last trading day of each month.
- Trend signals are normalized by the closing price on the last trading day of the month.
- Cross-sectional regressions are run each month, regressing monthly stock returns on the trend signals to obtain time-series of the coefficients of the trend signals.
- The expected return for the next month is estimated using the moving averages of the coefficients in the 12 months prior to the actual month and the moving signals for the actual month.
- Stocks are sorted into quintiles based on predicted return.
- The investor goes long on stocks with the highest predicted return and shorts stocks with the lowest predicted return.
- The portfolio is equally weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1926-2010
- **Annual Return:** 12.59%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.67
- **Annual Standard Deviation:** 12.75%

## Python code

### Backtrader

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    def __init__(self):
        # Define investment universe
        self.universe = bt.feeds.YahooFinanceData(dataname=['AAPL', 'MSFT', 'AMZN', ...], fromdate=datetime(2022,1,1), todate=datetime(2022,12,31))

    def next(self):
        # Implement trading rules to select largest stocks based on market cap
        # For each month using 3-, 5-, and 20-day moving averages to calculate trend signals
        # Normalize trend signals
        # Run cross-sectional regressions to obtain coefficients of trend signals
        # Estimate expected returns with moving averages of coefficients and moving signals
        # Assign stocks into quintiles based on predicted return
        # Go long on stocks with highest predicted return
        # Short stocks with lowest predicted return
        # Equally weight portfolio and rebalance monthly
```

Note: This is just a skeleton of the code and does not include the specifics of the trading rules. The actual code would require additional research and data manipulation.