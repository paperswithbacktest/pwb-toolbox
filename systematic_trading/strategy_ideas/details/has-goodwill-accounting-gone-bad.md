<div align="center">
  <h1>Has Goodwill Accounting Gone Bad?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1466271)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ listed stocks
- Annual stock sorting: Based on previous fiscal year’s Return on Assets (ROA)
- Select stocks with lowest ROA
- Further sort by goodwill divided by total assets
- Short stocks with highest goodwill and lowest ROA
- Maintain equally weighted portfolio
- Rebalance portfolio annually

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 2002-2008
- **Annual Return:** 17.4%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.72
- **Annual Standard Deviation:** 18.56%

## Python code

### Backtrader

```python
import backtrader as bt

class GoodwillShort(bt.Strategy):
    params = (
        ("rebalance_days", 252),
    )

    def __init__(self):
        self.roa = bt.ind.ReturnOnAssets()
        self.goodwill_ratio = bt.ind.Goodwill() / bt.ind.TotalAssets()
        self.order_list = []

    def next(self):
        if len(self.data) % self.params.rebalance_days == 0:
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        self.cancel_all_orders()
        roa_ranked_stocks = sorted(self.datas, key=lambda stock: stock.roa[0])
        lowest_roa_stocks = roa_ranked_stocks[:int(len(roa_ranked_stocks) * 0.1)]
        sorted_by_goodwill_ratio = sorted(lowest_roa_stocks, key=lambda stock: stock.goodwill_ratio[0], reverse=True)
        portfolio_size = len(sorted_by_goodwill_ratio)
        weight = 1.0 / portfolio_size
        for data in self.datas:
            if data in sorted_by_goodwill_ratio:
                target_value = self.broker.getvalue() * weight
                self.order_target_value(data, -target_value)
            else:
                self.order_target_value(data, 0)

    def cancel_all_orders(self):
        for order in self.order_list:
            self.cancel(order)
        self.order_list = []

if __name__ == "__main__":
    cerebro = bt.Cerebro()
    # Add data feeds for stocks listed on NYSE, AMEX, and NASDAQ
    # ...

    cerebro.addstrategy(GoodwillShort)
    cerebro.run()
```

Please note that this code snippet is a starting point and you would need to add data feeds for the stocks listed on NYSE, AMEX, and NASDAQ, configure the desired backtesting period, and potentially adjust other settings to fit your specific requirements.