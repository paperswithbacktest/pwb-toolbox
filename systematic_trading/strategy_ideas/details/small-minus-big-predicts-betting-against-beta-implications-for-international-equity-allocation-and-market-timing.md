<div align="center">
  <h1>Small-Minus-Big Predicts Betting-Against-Beta: Implications for International Equity Allocation and Market Timing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3227047)

## Trading rules

- Investment universe consists of stocks of the 24 developed markets covered by AQR factors
- Sort the betting against beta (BAB) strategies in the 24 examined markets on the past average geometric return on the small minus big (SMB) factors in the respective countries
- Divide the countries (and their stocks) into two groups, those with the 20% of highest and 20% of the lowest average SMB return in months t-3 to t-1
- Form a long portfolio which contains the BAB strategy for the countries with the highest average SMB return in months t-3 to t-1
- Form a short portfolio which contains the BAB strategy for the countries with the lowest average SMB return in months t-3 to t-1
- The strategy is equally-weighted
- The strategy is rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1989-2018
- **Annual Return:** 19%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.13
- **Annual Standard Deviation:** 13.27%

## Python code

### Backtrader

```python
# Import necessary modules
import backtrader as bt

# Define the investment universe
universe = ['Stock1', 'Stock2', ... 'StockN']

# Define the betting against beta (BAB) strategy and SMB factor
class BETTING_AGAINST_BETA(bt.Strategy):
    # Define the past average geometric return on SMB factors
    @staticmethod
    def compute_smb_return(data, t):
        smb_return = ... # Calculate SMB return for month t
        return smb_return

    # Determine which countries to trade for long and short portfolios
    def check_smb_return(self, data):
        smb_returns = [] # List of SMB returns for each country
        for stock in data._name2idx.keys(): # Loop over stocks in universe
            smb_return = self.compute_smb_return(data[stock], self.datetime.date(-1)) # Compute SMB return for previous month
            smb_returns.append(smb_return)
        smb_mean = sum(smb_returns) / len(smb_returns) # Compute mean SMB return
        smb_threshold = 0.2 * smb_mean # Calculate 20% threshold for high and low SMB countries
        high_smb = [universe[i] for i in range(len(smb_returns)) if smb_returns[i] >= smb_threshold] # Countries with high SMB return
        low_smb = [universe[i] for i in range(len(smb_returns)) if smb_returns[i] <= -smb_threshold] # Countries with low SMB return
        return high_smb, low_smb

    # Define long and short portfolios
    def create_portfolios(self, data, high_smb, low_smb):
        long_portfolio = bt.Portfolio() # Long portfolio
        for stock in high_smb:
            long_portfolio += bt.Strategy(data[stock], BETTING_AGAINST_BETA)
        short_portfolio = bt.Portfolio() # Short portfolio
        for stock in low_smb:
            short_portfolio += bt.Strategy(data[stock], BETTING_AGAINST_BETA)
        return long_portfolio, short_portfolio

    # Define strategy
    def __init__(self):
        # Determine high and low SMB return countries
        high_smb, low_smb = self.check_smb_return(self.datas)
        # Create long and short portfolios
        long_portfolio, short_portfolio = self.create_portfolios(self.datas, high_smb, low_smb)
        # Equal-weight portfolios
        self.broker.set_coc(True)
        long_portfolio.set_coc(True)
        short_portfolio.set_coc(True)
        self.bb = self.buy(size=1, exectype=bt.Order.Close)
        self.sb = self.sell(size=1, exectype=bt.Order.Close)
        return

    # Monthly rebalancing
    def next(self):
        # Rebalance
        if self.datetime.date().day == 1:
            self.broker.set_coc(True)
            long_portfolio.set_coc(True)
            short_portfolio.set_coc(True)
            self.bb = self.buy(size=1, exectype=bt.Order.Close)
            self.sb = self.sell(size=1, exectype=bt.Order.Close)
            return
```

Note: This code is incomplete and may need to be adjusted depending on the specifics of the betting against beta (BAB) strategies and the small minus big (SMB) factors used in the analysis.