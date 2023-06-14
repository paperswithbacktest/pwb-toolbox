<div align="center">
  <h1>Informed Trading of Out-of-the-Money Options and Market Efficiency</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2803724)

## Trading rules

- Investment universe: Stocks with OTM options data in IvyDB OptionMetrics database
- Stock prices source: CRSP database
- Sort stocks by weekly OTMPC ratio into deciles
- Buy bottom decile (lowest relative OTM put trading volume)
- Sell top decile
- Portfolio: Value-weighted
- Rebalance: Weekly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1996-2014
- **Annual Return:** 10.37%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.58
- **Annual Standard Deviation:** 10.99%

## Python code

### Backtrader

```python
import backtrader as bt

class OTMPCStrategy(bt.Strategy):
    def __init__(self):
        self.otmpc = dict()

    def next(self):
        # Sort stocks by weekly OTMPC ratio into deciles
        stocks = self.datas
        for stock in stocks:
            self.otmpc[stock] = stock.lines.otmpc[0]  # Assuming the OTMPC ratio is stored as a line in the stock data

        sorted_stocks = sorted(self.otmpc.items(), key=lambda x: x[1])
        bottom_decile = sorted_stocks[:len(sorted_stocks) // 10]
        top_decile = sorted_stocks[-(len(sorted_stocks) // 10):]

        # Buy bottom decile (lowest relative OTM put trading volume)
        for stock, _ in bottom_decile:
            self.order_target_percent(stock, target=1 / len(bottom_decile))

        # Sell top decile
        for stock, _ in top_decile:
            self.order_target_percent(stock, target=-1 / len(top_decile))

cerebro = bt.Cerebro()
cerebro.addstrategy(OTMPCStrategy)

# Add stocks data and indicators here
# ...

cerebro.run()
```

Please note that this code snippet assumes you have the required stock and options data available and properly formatted for Backtrader. You will need to add the data feeds and any required indicators (e.g., the OTMPC ratio) to the code. This snippet only provides the core logic of the strategy and does not include data loading, indicators calculation or full implementation.