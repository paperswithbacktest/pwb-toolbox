<div align="center">
  <h1>Is the Accrual Anomaly a Global Anomaly?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=782726)

## Trading rules

- Investment Universe: NYSE, AMEX, and NASDAQ stocks
- Calculate Balance Sheet Accruals (BS_ACC): BS_ACC = (∆CA - ∆Cash) - (∆CL - ∆STD - ∆ITP) - Dep
    - ∆CA: Annual change in current assets
    - ∆Cash: Change in cash and cash equivalents
    - ∆CL: Change in current liabilities
    - ∆STD: Change in debt within current liabilities
    - ∆ITP: Change in income taxes payable
    - Dep: Annual depreciation and amortization expense
- Sort stocks into deciles based on accruals
- Go long on lowest accrual stocks, short on highest accrual stocks
- Rebalance portfolio annually in May (post-earnings releases)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1966-2003
- **Annual Return:** 7.5%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.34
- **Annual Standard Deviation:** 10.26%

## Python code

### Backtrader

```python
import backtrader as bt

class AccrualAnomaly(bt.Strategy):
    def __init__(self):
        self.accruals = {}

    def next(self):
        if self.data.datetime.date().month != 5:  # Rebalance only in May
            return

        self.accruals.clear()

        for data in self.datas:
            ca = data.current_assets  # Replace with actual attribute name
            cash = data.cash_equivalents  # Replace with actual attribute name
            cl = data.current_liabilities  # Replace with actual attribute name
            std = data.short_term_debt  # Replace with actual attribute name
            itp = data.income_taxes_payable  # Replace with actual attribute name
            dep = data.depreciation_amortization_expense  # Replace with actual attribute name

            delta_ca = ca - ca(-1)
            delta_cash = cash - cash(-1)
            delta_cl = cl - cl(-1)
            delta_std = std - std(-1)
            delta_itp = itp - itp(-1)

            bs_acc = (delta_ca - delta_cash) - (delta_cl - delta_std - delta_itp) - dep
            self.accruals[data] = bs_acc

        sorted_stocks = sorted(self.datas, key=lambda d: self.accruals[d])
        low_decile = int(len(sorted_stocks) * 0.1)
        high_decile = int(len(sorted_stocks) * 0.9)
        long_stocks = sorted_stocks[:low_decile]
        short_stocks = sorted_stocks[high_decile:]

        self.sell_stocks(short_stocks)
        self.buy_stocks(long_stocks)

    def sell_stocks(self, short_stocks):
        for stock in short_stocks:
            self.sell(data=stock)

    def buy_stocks(self, long_stocks):
        for stock in long_stocks:
            self.buy(data=stock)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for NYSE, AMEX, and NASDAQ stocks here
    # Replace 'data_feed' with actual data feed objects
    for data_feed in data_feeds:
        cerebro.adddata(data_feed)

    cerebro.addstrategy(AccrualAnomaly)
    cerebro.run()
```

This code snippet provides a basic implementation of the Accrual Anomaly trading strategy in Backtrader. You’ll need to add your data feeds for NYSE, AMEX, and NASDAQ stocks to complete the implementation.