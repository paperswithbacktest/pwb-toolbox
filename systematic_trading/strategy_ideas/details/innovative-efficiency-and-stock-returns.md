<div align="center">
  <h1>Innovative Efficiency and Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1799675)

## Trading rules

- Focus on small-cap stocks from NYSE, AMEX, and NASDAQ, excluding financial firms, CEFs, ADRs, and REITs
- Utilize NBER patent database for patent information
- Measure innovative efficiency using patents per R&D expenses (2 years prior) as the primary metric
- Include only stocks with at least one granted patent
- Sort stocks into three groups based on their innovative efficiency
- Go long on high-efficiency stocks and short on low-efficiency stocks
- Hold the portfolio for 12 months before rebalancing

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1982-2007
- **Annual Return:** 6.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.4
- **Annual Standard Deviation:** 7%

## Python code

### Backtrader

```python
import backtrader as bt

class InnovativeEfficiencyStrategy(bt.Strategy):
    def __init__(self):
        self.rnd_exp = dict()

    def prenext(self):
        self.next()

    def next(self):
        if len(self.datas) < 2:
            return

        if self.datetime.date(-12).month != self.datetime.date().month:
            return

        self.rebalance_portfolio()

    def rebalance_portfolio(self):
        stocks_with_patents = [
            data for data in self.datas
            if data._name in self.rnd_exp and data.patents > 0
        ]

        if not stocks_with_patents:
            return

        stocks_with_patents.sort(key=lambda data: data.patents / self.rnd_exp[data._name][-2], reverse=True)
        third = len(stocks_with_patents) // 3
        long_stocks = stocks_with_patents[:third]
        short_stocks = stocks_with_patents[-third:]

        for data in long_stocks:
            self.order_target_percent(data, target=1.0 / len(long_stocks))

        for data in short_stocks:
            self.order_target_percent(data, target=-1.0 / len(short_stocks))

        for data in self.datas:
            if data not in long_stocks + short_stocks:
                self.order_target_percent(data, target=0.0)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}")
            elif order.issell():
                self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

    def log(self, txt, dt=None):
        dt = dt or self.datetime.date()
        print(f"{dt.isoformat()}, {txt}")


def run_strategy():
    cerebro = bt.Cerebro()

    # Load data and filter stocks
    # Add your own data loading and filtering code here

    # Add the strategy to the cerebro instance
    cerebro.addstrategy(InnovativeEfficiencyStrategy)

    # Set the starting cash
    cerebro.broker.setcash(100000.0)

    # Run the backtest
    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())


if __name__ == "__main__":
    run_strategy()
```

Please note that this code is a basic framework for the trading strategy in Backtrader. You will need to implement your own data loading and filtering code to obtain the small-cap stocks from NYSE, AMEX, and NASDAQ while excluding financial firms, CEFs, ADRs, and REITs. Additionally, you will need to incorporate the NBER patent database for patent information.