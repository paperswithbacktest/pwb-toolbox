<div align="center">
  <h1>Illiquidity and Stock Returns: A Revisit</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3257038)

## Trading rules

- Select top 3,500 companies from NYSE, AMEX, and NASDAQ based on market capitalization
    - Stock’s per-share price must be at least $2
    - Market capitalization must be no less than $10 million
    - Exclude REITs, warrants, ADRs, ETFs, Americus Trust Components, and closed-end funds
- Divide stocks into quartiles based on market capitalization
- Focus on stocks in the lowest market-cap quartile
    - Divide these stocks into quartiles based on turnover in the last 12 months
- Go long on stocks with the lowest turnover
- Go short on stocks with the highest turnover
- Rebalance the portfolio once a year (in December)
- Weight stocks equally in the portfolio

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1982-2007
- **Annual Return:** 7.7%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.35
- **Annual Standard Deviation:** 10.5%

## Python code

### Backtrader

```python
import backtrader as bt

class LowLiquidityStrategy(bt.Strategy):
    def __init__(self):
        self.rank_market_cap = None
        self.rank_turnover = None
    
    def next(self):
        if self.datetime.date().month == 12 and self.datetime.date().day == 31:
            # Filter stocks by market cap and per-share price
            filtered_stocks = [d for d in self.datas if d.close[0] >= 2 and d.market_cap >= 10000000 and not d.is_excluded]
            
            # Sort by market cap and select top 3500
            sorted_by_market_cap = sorted(filtered_stocks, key=lambda d: d.market_cap, reverse=True)[:3500]
            
            # Divide stocks into quartiles by market cap
            quartile_size = len(sorted_by_market_cap) // 4
            lowest_market_cap_quartile = sorted_by_market_cap[-quartile_size:]
            
            # Divide lowest market cap quartile stocks into quartiles based on turnover
            sorted_by_turnover = sorted(lowest_market_cap_quartile, key=lambda d: d.turnover)
            turnover_quartile_size = len(sorted_by_turnover) // 4
            lowest_turnover_quartile = sorted_by_turnover[:turnover_quartile_size]
            highest_turnover_quartile = sorted_by_turnover[-turnover_quartile_size:]
            
            # Go long on stocks with the lowest turnover
            for data in lowest_turnover_quartile:
                self.order_target_percent(data, target=1.0 / len(lowest_turnover_quartile))
            
            # Go short on stocks with the highest turnover
            for data in highest_turnover_quartile:
                self.order_target_percent(data, target=-1.0 / len(highest_turnover_quartile))
            
            # Close positions for the stocks not in the lowest or highest turnover quartile
            for data in self.datas:
                if data not in lowest_turnover_quartile and data not in highest_turnover_quartile:
                    self.close(data)

cerebro = bt.Cerebro()
cerebro.addstrategy(LowLiquidityStrategy)

# Add your data feeds to cerebro here

cerebro.run()
```

Note that this code is a starting point for implementing the trading rules you provided. You will need to add your data feeds to `cerebro` and ensure that the data feeds have the necessary information, such as market capitalization, turnover, and any exclusion criteria (REITs, warrants, ADRs, ETFs, Americus Trust Components, and closed-end funds). Additionally, the code assumes the data feeds are daily. You may need to adjust it if you are using a different frequency.