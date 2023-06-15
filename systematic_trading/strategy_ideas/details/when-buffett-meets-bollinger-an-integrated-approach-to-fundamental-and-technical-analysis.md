<div align="center">
  <h1>When Buffett Meets Bollinger: An Integrated Approach to Fundamental and Technical Analysis</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3330402)

## Trading rules

- Investment universe: non-financial NYSE and AMEX-listed firms (excluding foreign companies, closed-end funds, REITs, ADRs, stocks priced below $1, and negative book-to-market ratio stocks)
- Narrow universe to top quintile of firms with highest book-to-market ratio
- Perform triple sort:
    1. Select top quintile (winner) and bottom quintile (loser) stocks based on 12-month momentum
    2. Calculate BOS ratio (covariance of 12-month return and average volume)
    3. Choose lowest BOS ratio stocks from winner portfolio and highest BOS ratio stocks from loser portfolio
- Calculate FSCORE for each stock in winner and loser portfolios
- Go long on top quintile of winner stocks with highest FSCORE ratio and short on bottom quintile of loser stocks with lowest FSCORE ratio
- Rebalance one-third of the portfolio monthly
- Optimal holding period: 3 months
- Equal stock weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1982-2008
- **Annual Return:** 48.67%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.99
- **Annual Standard Deviation:** 45%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class TripleSort(bt.Strategy):

    def __init__(self):
        self.stock_filter()

    def stock_filter(self):
        # Investment universe
        nyse_amex = self.get_data()  # Assume this function returns a dataframe of NYSE and AMEX-listed firms
        non_financial = nyse_amex[nyse_amex['industry'] != 'financial']
        filtered_stocks = non_financial[(non_financial['price'] >= 1) & (non_financial['book_to_market'] > 0)]

        # Narrow universe to top quintile of firms with highest book-to-market ratio
        top_quintile = filtered_stocks.nlargest(int(len(filtered_stocks) * 0.2), 'book_to_market')

        # Perform triple sort
        winner_loser_stocks = self.triple_sort(top_quintile)

        # Rebalance one-third of the portfolio monthly
        self.rebalance_portfolio(winner_loser_stocks)

    def triple_sort(self, top_quintile):
        # 1. Select top and bottom quintile stocks based on 12-month momentum
        top_quintile['momentum'] = top_quintile['price'].pct_change(12)
        winners = top_quintile.nlargest(int(len(top_quintile) * 0.2), 'momentum')
        losers = top_quintile.nsmallest(int(len(top_quintile) * 0.2), 'momentum')

        # 2. Calculate BOS ratio (covariance of 12-month return and average volume)
        winners['BOS_ratio'] = winners.apply(lambda row: np.cov(row['momentum'], row['average_volume'])[0][1], axis=1)
        losers['BOS_ratio'] = losers.apply(lambda row: np.cov(row['momentum'], row['average_volume'])[0][1], axis=1)

        # 3. Choose lowest BOS ratio stocks from winner portfolio and highest BOS ratio stocks from loser portfolio
        winners_low_bos = winners.nsmallest(int(len(winners) * 0.2), 'BOS_ratio')
        losers_high_bos = losers.nlargest(int(len(losers) * 0.2), 'BOS_ratio')

        # Calculate FSCORE for each stock in winner and loser portfolios
        winners_low_bos['FSCORE'] = self.calculate_FSCORE(winners_low_bos)
        losers_high_bos['FSCORE'] = self.calculate_FSCORE(losers_high_bos)

        return winners_low_bos, losers_high_bos

    def calculate_FSCORE(self, stocks):
        # Assume this function returns the FSCORE for each stock in the dataframe
        pass

    def rebalance_portfolio(self, winner_loser_stocks):
        winners_low_bos, losers_high_bos = winner_loser_stocks

        # Go long on top quintile of winner stocks with highest FSCORE ratio
        long_stocks = winners_low_bos.nlargest(int(len(winners_low_bos) * 0.2), 'FSCORE')

        # Short on bottom quintile of loser stocks with lowest FSCORE ratio
        short_stocks = losers_high_bos.nsmallest(int(len(losers_high_bos) * 0.2), 'FSCORE')

        # Rebalance one-third of the portfolio monthly
        num_stocks_to_rebalance = int(len(long_stocks) * 0.33)
        long_stocks_to_rebalance = long_stocks
```