<div align="center">
  <h1>Slow Trading and Stock Return Predictability</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2671237)

## Trading rules

- Trading instrument: IShares Russell 2000 ETF (IWM).
- Monitor monthly performance of large cap stocks which are defined in source academic paper as stocks from 1st to 3rd decile and sorted by market capitalization.
- Large cap ETF or index fund could be used as a proxy.
- Investor is long in the IWM ETF during months following a positive value weighted return of large cap stocks.
- Investor will be in cash (with zero interest) during other months.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2000-2014
- **Annual Return:** 9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.73
- **Annual Standard Deviation:** 12.33%

## Python code

### Backtrader

```python
# Import required modules
from datetime import datetime
import backtrader as bt

# Define the strategy class
class MonthlyPerformanceStrategy(bt.Strategy):
    def __init__(self):
        self.iwm = self.datas[0]  # IWM ETF data
        self.large_cap = self.datas[1]  # Large cap ETF/index fund data
        self.monthly_returns = []  # List to store monthly returns of the large cap stocks
        
        # Define the months and years for which we want to monitor performance
        self.months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        self.years = [year for year in range(2000, 2022)]
        
        self.add_timer(
            when=bt.Timer.SESSION_START,
            month=self.months,
            year=self.years,
        )

    def notify_timer(self, timer, when, *args, **kwargs):
        # Check if the current month is in our list of monitored months
        if timer.month in self.months:
            # Get the closing prices of the large cap stocks for the current month
            large_cap_returns = [d.close for d in self.datas[1:]]
            
            # Sort the large cap stocks by market capitalization
            sorted_large_cap_returns = sorted(large_cap_returns)
            
            # Split the sorted returns into 10 deciles
            deciles = [
                sorted_large_cap_returns[i:i + len(sorted_large_cap_returns) // 10]
                for i in range(0, len(sorted_large_cap_returns), len(sorted_large_cap_returns) // 10)
            ]
            
            # Get the 1st to 3rd decile of returns (large cap stocks)
            large_cap_returns = deciles[0] + deciles[1] + deciles[2]
            
            # Calculate the value weight of the large cap stocks
            total_cap = sum(large_cap_returns)
            weights = [cap / total_cap for cap in large_cap_returns]
            
            # Calculate the value weighted return of the large cap stocks
            large_cap_return = sum([w * r for w, r in zip(weights, large_cap_returns)])
            
            # Append the monthly return to the list of monthly returns
            self.monthly_returns.append(large_cap_return)
            
            # If the value weighted return of large cap stocks is positive, buy IWM ETF
            if large_cap_return > 0:
                self.buy(size=1)
        else:
            # If the current month is not in our list of monitored months, sell the IWM ETF
            self.sell(size=1)

# Define the backtest
if __name__ == '__main__':
    cerebro = bt.Cerebro()
    
    # Add data feeds
    iwm_data = bt.feeds.YahooFinanceData(dataname='IWM', fromdate=datetime(2000, 1, 1), todate=datetime(2022, 1, 1))
    large_cap_data = bt.feeds.YahooFinanceData(dataname='SPY', fromdate=datetime(2000, 1, 1), todate=datetime(2022, 1, 1))
    cerebro.adddata(iwm_data)
    cerebro.adddata(large_cap_data)
    
    # Add strategy
    cerebro.addstrategy(MonthlyPerformanceStrategy)
    
    # Set cash to zero (with zero interest)
    cerebro.broker.set_cash(0)
    
    # Run the backtest
    cerebro.run()
    
    # Print the final portfolio value
    print('Final portfolio value: %.2f' % cerebro.broker.get_value())
```