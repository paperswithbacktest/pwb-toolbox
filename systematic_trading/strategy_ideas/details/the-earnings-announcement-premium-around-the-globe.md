<div align="center">
  <h1>The Earnings Announcement Premium Around the Globe</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1872183)

## Trading rules

- Investment universe: All stocks from CRSP database
- Monthly ranking: Stocks ranked in ascending order based on volume concentration ratio (previous 16 announcement months volume / total volume in previous 48 months)
- Portfolio assignment: Stocks divided into 5 quintile portfolios
- Further categorization: Within each quintile, stocks split into expected announcers and expected non-announcers using predictions from the previous year
- Portfolio weighting: Value-weighted stocks within each portfolio
- Monthly rebalancing: Portfolios rebalanced to maintain value weights
- Long-short investment: Zero-cost portfolio holding high volume expected announcers, selling short high volume expected non-announcers

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1973-2004
- **Annual Return:** 18.36%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.89
- **Annual Standard Deviation:** 16.12%

## Python code

### Backtrader

Here is a simple Backtrader python code for the trading strategy described:

```python
import backtrader as bt

class EarningsAnnouncementPremium(bt.Strategy):
    params = (
        ('quintiles', 5),  # Number of quintiles for portfolio construction
    )

    def __init__(self):
        self.rank_data = {}  # Dictionary to store ranking data for each stock

    def prenext(self):
        self.next()  # Call next() even when data is not available for all tickers

    def next(self):
        self.rank_stocks()  # Rank stocks based on volume concentration
        self.build_portfolios()  # Build portfolios based on quintiles
        self.rebalance()  # Rebalance the portfolios

    def rank_stocks(self):
        for d in self.datas:
            volume_concentration = sum(d.volume.get(size=-16)) / sum(d.volume.get(size=-48))
            self.rank_data[d] = volume_concentration
        self.rank_data = dict(sorted(self.rank_data.items(), key=lambda x: x[1]))

    def build_portfolios(self):
        total_stocks = len(self.datas)
        stocks_per_quintile = total_stocks // self.params.quintiles

        self.portfolios = {}
        for i in range(self.params.quintiles):
            self.portfolios[i] = {'expected_announcers': [], 'expected_non_announcers': []}

            start = i * stocks_per_quintile
            end = start + stocks_per_quintile if i < self.params.quintiles - 1 else total_stocks

            for j, (d, _) in enumerate(self.rank_data.items()):
                if start <= j < end:
                    if d.expected_announcer:  # Assuming an attribute `expected_announcer` exists in the data feed
                        self.portfolios[i]['expected_announcers'].append(d)
                    else:
                        self.portfolios[i]['expected_non_announcers'].append(d)

    def rebalance(self):
        total_value = self.broker.getvalue()
        weight_per_stock = total_value / len(self.portfolios[self.params.quintiles - 1]['expected_announcers'])

        for d in self.portfolios[self.params.quintiles - 1]['expected_announcers']:
            size = weight_per_stock / self.data.close[0]
            self.order_target_size(data=d, target=size)

        for d in self.portfolios[self.params.quintiles - 1]['expected_non_announcers']:
            size = -weight_per_stock / self.data.close[0]
            self.order_target_size(data=d, target=size)

cerebro = bt.Cerebro()

# Add your data feeds here
data_feed_1 = bt.feeds.YourFirstDataFeed()
data_feed_2 = bt.feeds.YourSecondDataFeed()

cerebro.adddata(data_feed_1)
cerebro.adddata(data_feed_2)

cerebro.addstrategy(EarningsAnnouncementPremium)

cerebro.run()
```

Please note that this code assumes the data feeds have an attribute `expected_announcer` for each stock, indicating whether the stock is an expected announcer or not. You’ll need to provide the data feeds and Cerebro setup for running the strategy. This code is just a simple starting point and might need further modifications to fit your specific requirements.