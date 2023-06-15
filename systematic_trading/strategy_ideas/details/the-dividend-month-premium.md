<div align="center">
  <h1>The Dividend Month Premium</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1930620)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ stocks (from CRSP Compustat database)
- Exclude shares priced below $5
- Divide stocks into two groups:
    - Expected to pay a dividend in current month
    - Not expected to pay a dividend in current month
- Predicted dividend criteria:
    - Quarterly dividend paid in months t-3, t-6, t-9, or t-12
    - Semi-annual dividend paid in months t-6 or t-12
    - Annual dividend paid in month t-12
    - Dividend of unknown frequency paid in months t-3, t-6, t-9, or t-12
- Go long on stocks with expected dividend payments in current month
- Equally weighted portfolio, rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1927-2009
- **Annual Return:** 17.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.7
- **Annual Standard Deviation:** 20%

## Python code

### Backtrader

```python
import backtrader as bt

class DividendMonthAnomaly(bt.Strategy):
    def __init__(self):
        self.dividends = {}  # Dictionary to store dividend dates for each stock

    def next(self):
        current_month = self.datetime.date(0).month  # Get current month

        long_stocks = []  # List to store stocks expected to pay dividends

        for d in self.datas:
            if d.close[0] < 5:  # Skip stocks with a price below $5
                continue

            if self.expected_dividend(d, current_month):  # Check if stock is expected to pay dividend
                long_stocks.append(d)

        position_size = 1 / len(long_stocks)  # Calculate position size

        for stock in long_stocks:
            self.order_target_percent(stock, target=position_size)  # Go long on stocks with expected dividends

    def expected_dividend(self, data, current_month):
        dividends = self.dividends.get(data._name, [])

        for dividend_date in dividends:
            if (
                (dividend_date.month + 3) % 12 == current_month or
                (dividend_date.month + 6) % 12 == current_month or
                (dividend_date.month + 9) % 12 == current_month or
                (dividend_date.month + 12) % 12 == current_month
            ):
                return True

        return False

    def add_dividend_data(self, stock_name, dividend_dates):
        self.dividends[stock_name] = dividend_dates
```