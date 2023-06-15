<div align="center">
  <h1>The Effect of Treasury Auctions on 10-Year Treasury Note Futures</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3315135)

## Trading rules

- Go short on 2-year notes and long on duration-matching 10-year notes and 6-month T-bills 10 days before the auction
- Maintain zero investment portfolio until auction day
- Reverse positions on auction day
- Hold reversed positions for 10 days post-auction
- Possible to simulate using futures or CFDs trading

## Statistics

- **Markets Traded:** Bonds
- **Period of Rebalancing:** Daily
- **Backtest period:** 1998-2008
- **Annual Return:** 5.74%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.84
- **Annual Standard Deviation:** 6.83%

## Python code

### Backtrader

Here is the Backtrader Python code for the trading rules you provided:

```python
import backtrader as bt
import datetime

class TreasuryAuctionStrategy(bt.Strategy):
    def __init__(self):
        self.auction_dates = [datetime.date(YYYY, MM, DD), ...]  # Replace with actual auction dates
        self.pre_auction = 10  # Number of days before the auction to enter positions
        self.post_auction = 10  # Number of days after the auction to close positions

    def next(self):
        current_date = self.data.datetime.date(0)
        for auction_date in self.auction_dates:
            days_to_auction = (auction_date - current_date).days

            if days_to_auction == self.pre_auction:
                # 10 days before auction, short 2-year notes and long 10-year notes and 6-month T-bills
                self.sell(data=self.data2)  # Sell 2-year notes
                self.buy(data=self.data3)  # Buy 10-year notes
                self.buy(data=self.data4)  # Buy 6-month T-bills

            elif current_date == auction_date:
                # Reverse positions on auction day
                self.buy(data=self.data2)  # Buy 2-year notes
                self.sell(data=self.data3)  # Sell 10-year notes
                self.sell(data=self.data4)  # Sell 6-month T-bills

            elif days_to_auction == -self.post_auction:
                # Close positions 10 days after auction
                self.close(data=self.data2)  # Close 2-year notes
                self.close(data=self.data3)  # Close 10-year notes
                self.close(data=self.data4)  # Close 6-month T-bills
                break

# Replace with your data feeds for 2-year notes, 10-year notes, and 6-month T-bills
data2 = ...
data3 = ...
data4 = ...

cerebro = bt.Cerebro()
cerebro.addstrategy(TreasuryAuctionStrategy)
cerebro.adddata(data2)
cerebro.adddata(data3)
cerebro.adddata(data4)
cerebro.run()
```

Please make sure to replace the placeholders with your data feeds and actual auction dates. This code assumes you have data feeds for 2-year notes, 10-year notes, and 6-month T-bills.