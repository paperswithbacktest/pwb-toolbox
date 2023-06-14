<div align="center">
  <h1>Implementability of Trading Strategies Based on Accounting Information: Piotroski (2000) Revisited</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2428946)

## Trading rules

- Investment universe: Top 20% high book-to-market firms
- Scoring system: Nine binary signals based on profitability and value-specific financial measures:
    1. Positive ROA: 1 point
    2. Positive CFO: 1 point
    3. Positive change in ROA: 1 point
    4. CFO > ROA (Accrual): 1 point
    5. Decreased leverage ratio: 1 point
    6. Improved liquidity ratio: 1 point
    7. No common equity issued in the previous year: 1 point
    8. Positive change in margin: 1 point
    9. Positive change in turnover: 1 point
- Portfolio creation: Begin in May after companies report financial statements for the previous year
- Long positions: Stocks with summary scores of 8 or 9
- Short positions: Stocks with summary scores of 0 or 1
- Portfolio weighting: Equally weighted
- Rebalancing: Yearly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1976-1996
- **Annual Return:** 23%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.03
- **Annual Standard Deviation:** 18.4%

## Python code

### Backtrader

```python
import backtrader as bt

class ValueInvesting(bt.Strategy):
    def __init__(self):
        pass
    
    def next(self):
        orders = []
        
        for i, d in enumerate(self.datas):
            # Get data for each stock
            roa = d.roa[0]
            cfo = d.cfo[0]
            delta_roa = d.roa[0] - d.roa[-1]
            accrual = cfo > roa
            leverage_ratio = d.leverage_ratio[0]
            liquidity_ratio = d.liquidity_ratio[0]
            common_equity = d.common_equity[0]
            delta_margin = d.margin[0] - d.margin[-1]
            delta_turnover = d.turnover[0] - d.turnover[-1]
            
            # Calculate score
            score = 0
            score += int(roa > 0)
            score += int(cfo > 0)
            score += int(delta_roa > 0)
            score += int(accrual)
            score += int(leverage_ratio < d.leverage_ratio[-1])
            score += int(liquidity_ratio > d.liquidity_ratio[-1])
            score += int(common_equity == 0)
            score += int(delta_margin > 0)
            score += int(delta_turnover > 0)
            
            # Add to orders
            orders.append((i, d, score))
        
        # Sort and filter stocks
        top_20_percent = sorted(orders, key=lambda x: x[2], reverse=True)[:int(len(orders) * 0.2)]
        
        # Create portfolio
        longs = [order for order in top_20_percent if order[2] in [8, 9]]
        shorts = [order for order in top_20_percent if order[2] in [0, 1]]
        
        # Calculate equal weights
        long_weight = 1 / len(longs) if longs else 0
        short_weight = -1 / len(shorts) if shorts else 0
        
        # Execute orders
        for i, d, score in longs:
            self.order_target_percent(d, target=long_weight)
        
        for i, d, score in shorts:
            self.order_target_percent(d, target=short_weight)

cerebro = bt.Cerebro()

# Add data feeds and other cerebro configurations here

cerebro.addstrategy(ValueInvesting)

results = cerebro.run()
```

Make sure to add your data feeds with the required data fields (ROA, CFO, leverage ratio, liquidity ratio, common equity, margin, turnover) for this strategy to work properly.