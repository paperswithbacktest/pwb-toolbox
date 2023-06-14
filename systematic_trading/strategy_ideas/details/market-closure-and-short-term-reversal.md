<div align="center">
  <h1>Market Closure and Short-Term Reversal</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2730304)

## Trading rules

- Investment universe: 11 commodity futures (Corn, Ethanol CBOT, Lean Hogs, Live Cattle, Lumber, Oats, Pork Bellies, Rough Rice, Soybean Meal, Soybeans, Wheat CBOT)
- Data source: TickData database
- Contract selection: Most liquid (nearest to delivery)
- Portfolio: Zero-investment, buy past overnight losers, sell past overnight winners
- Commodity weights: Formulas (1) and (4) on pages 8 and 9 of source paper
- Adjusted weight: Use 1/2 of source paper’s calculated weight to reduce yearly volatility (60%)
- Trading period: Open-to-close following formation period (close-open)
- Rebalancing: Daily

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2007-2014
- **Annual Return:** 45.75%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.47
- **Annual Standard Deviation:** 31.02%

## Python code

### Backtrader

```python
import backtrader as bt

class CommodityReversal(bt.Strategy):
    params = dict(
        weight_factor=0.5,
    )

    def __init__(self):
        self.overnight_returns = {}
        self.weights = {}
        self.position_size = {}

    def next(self):
        for d in self.datas:
            symbol = d._name
            close = d.close[0]
            open = d.open[0]
            prev_close = d.close[-1]
            self.overnight_returns[symbol] = (open - prev_close) / prev_close

            # Calculate weights using formulas (1) and (4)
            # Replace calculated_weight with your own formula
            calculated_weight = 0.0
            self.weights[symbol] = calculated_weight

            # Adjust weight to reduce volatility
            self.position_size[symbol] = self.weights[symbol] * self.params.weight_factor * self.broker.get_cash()

        # Sort overnight returns
        sorted_returns = sorted(self.overnight_returns.items(), key=lambda x: x[1])
        # Buy past overnight losers and sell past overnight winners
        losers = sorted_returns[:len(sorted_returns) // 2]
        winners = sorted_returns[len(sorted_returns) // 2:]

        for symbol, _ in losers:
            data = self.getdatabyname(symbol)
            self.order_target_value(data, target=self.position_size[symbol])

        for symbol, _ in winners:
            data = self.getdatabyname(symbol)
            self.order_target_value(data, target=-self.position_size[symbol])

# Initialize Cerebro
cerebro = bt.Cerebro()

# Add data feeds for the 11 commodity futures
# Replace ... with the appropriate data feeds for each commodity future
data1 = bt.feeds.YourDataFeed(...)
data2 = bt.feeds.YourDataFeed(...)
# Add all 11 data feeds
cerebro.adddata(data1)
cerebro.adddata(data2)
# ...

# Add strategy
cerebro.addstrategy(CommodityReversal)

# Run backtest
results = cerebro.run()
```

Note: The provided code is a starting point and does not include specific data loading and the implementation of the formulas (1) and (4) for weight calculation from the source paper. You should complete these parts based on your own data source and the formulas mentioned in the paper.