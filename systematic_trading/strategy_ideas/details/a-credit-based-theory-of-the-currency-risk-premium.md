<div align="center">
  <h1>A Credit-Based Theory of the Currency Risk Premium</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3413785)

## Trading rules

- Investment universe: 29 USD currency pairs
- Estimate CDS term premium: Calculate difference between log of 10-year spread and log of 1-year spread for each country
- Monthly sorting: Organize currencies into three portfolios based on sovereign CDS term premia
- Long/short positions: Go long on highest CDS portfolio, short on lowest CDS portfolio
- Equal weighting: Maintain equal weight for each currency pair in the strategy
- Rebalancing: Adjust portfolio positions monthly

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2007-2017
- **Annual Return:** 4.84%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.82
- **Annual Standard Deviation:** 5.92%

## Python code

### Backtrader

```python
import backtrader as bt
import math

class CDSStrategy(bt.Strategy):
    def __init__(self):
        self.currency_pairs = self.datas
    
    def next(self):
        cds_premiums = []
        # Estimate CDS term premium for each country
        for pair in self.currency_pairs:
            ten_year_spread = pair.lines.close[0]  # Replace with 10-year spread data
            one_year_spread = pair.lines.close[0]  # Replace with 1-year spread data
            cds_premium = math.log(ten_year_spread) - math.log(one_year_spread)
            cds_premiums.append(cds_premium)
        # Sort currency pairs into three portfolios based on sovereign CDS term premia
        sorted_pairs = sorted(zip(self.currency_pairs, cds_premiums), key=lambda x: x[1])
        low_cds_portfolio = sorted_pairs[:len(sorted_pairs) // 3]
        high_cds_portfolio = sorted_pairs[-len(sorted_pairs) // 3:]
        # Calculate equal weights
        weight = 1 / len(self.currency_pairs)
        # Rebalance long/short positions
        for pair, premium in low_cds_portfolio:
            self.sell(pair, size=weight)
        for pair, premium in high_cds_portfolio:
            self.buy(pair, size=weight)
            
cerebro = bt.Cerebro()
# Add USD currency pairs
for pair in ['AUDUSD', 'EURUSD', 'GBPUSD']:  # Replace with the full list of 29 USD currency pairs
    data = bt.feeds.YahooFinanceData(dataname=pair)  # Replace with appropriate data feed
    cerebro.adddata(data)
cerebro.addstrategy(CDSStrategy)
cerebro.broker.set_cash(100000)  # Set initial cashcerebro.run()
```

Note: This code is a basic representation of the trading rules in Backtrader. You will need to replace placeholder values and choose the appropriate data feed for your specific use case.