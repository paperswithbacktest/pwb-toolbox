<div align="center">
  <h1>The Excess Returns of ‘Quality’ Stocks: A Behavioral Anomaly</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2717447)

## Trading rules

- Investment universe: Non-financial stocks from NYSE, Amex, and Nasdaq
- Big stocks: 90% of total market cap; Small stocks: 10% of total market cap
- Breakpoints: 30th and 70th percentiles of Earnings Quality ratios for large and small caps
- Ratio 1: Cash flow relative to reported earnings (high-quality = high cash flow)
- Ratio 2: Return on Equity (ROE) - long high-ROE firms (top 30%), short low-ROE firms (bottom 30%)
- Ratio 3: CF/A (cash flow to assets) - long firms with high cash flow to total assets
- Ratio 4: D/A (debt to assets) - long firms with low leverage, short firms with high leverage
- Composite quality metric: Percentile score for each stock on four quality metrics (0-400)
- Factor formation: Long top 30% and short bottom 30% of small-cap and large-cap stocks, cap-weighting individual stocks within portfolios
- Rebalance: Yearly, at the end of each June

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1988-2012
- **Annual Return:** 7.95%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.67
- **Annual Standard Deviation:** 5.91%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd

class EarningsQuality(bt.Strategy):
    params = (
        ('rebalance_months', [6]), 
        ('percentiles', (30, 70)), 
        ('market_cap_ratio', 0.9),
        )

    def __init__(self):
        self.order = None
        self.buy_sell_signals = pd.DataFrame()

    def next(self):
        if self.order:
            return

        month = self.datetime.datetime().month
        if month in self.params.rebalance_months:
            self.rebalance()

    def rebalance(self):
        self.cancel(self.order)

        data = self.get_stock_data()
        large_stocks, small_stocks = self.split_market_cap(data)

        for stock_data in [large_stocks, small_stocks]:
            quality_scores = self.calculate_quality_scores(stock_data)
            long_stocks, short_stocks = self.select_long_short_stocks(quality_scores)

            for stock, row in long_stocks.iterrows():
                self.order_target_percent(data=stock, target=row['weight'])

            for stock, row in short_stocks.iterrows():
                self.order_target_percent(data=stock, target=-row['weight'])

    def get_stock_data(self):
        stock_data = {}
        for stock in self.datas:
            stock_data[stock] = {
                'price': stock.close[0],
                'market_cap': stock.market_cap,
                'cash_flow': stock.cash_flow,
                'reported_earnings': stock.reported_earnings,
                'roe': stock.roe,
                'cf_a': stock.cf_a,
                'd_a': stock.d_a,
            }

        return pd.DataFrame(stock_data).T

    def split_market_cap(self, data):
        sorted_data = data.sort_values(by='market_cap', ascending=False)
        total_market_cap = sorted_data['market_cap'].sum()
        large_cap_threshold = total_market_cap * self.params.market_cap_ratio

        accumulated_market_cap = 0
        split_index = None

        for index, row in sorted_data.iterrows():
            accumulated_market_cap += row['market_cap']
            if accumulated_market_cap >= large_cap_threshold:
                split_index = index
                break

        return sorted_data.loc[:split_index], sorted_data.loc[split_index:]

    def calculate_quality_scores(self, stock_data):
        stock_data['ratio1'] = stock_data['cash_flow'] / stock_data['reported_earnings']
        stock_data['ratio1_pct'] = stock_data['ratio1'].rank(pct=True) * 100

        stock_data['ratio2_pct'] = stock_data['roe'].rank(pct=True) * 100
        stock_data['ratio3_pct'] = stock_data['cf_a'].rank(pct=True) * 100

        stock_data['ratio4'] = stock_data['d_a']
        stock_data['ratio4_pct'] = (1 - stock_data['ratio4'].rank(pct=True)) * 100

        stock_data['quality_score'] = stock_data[['ratio1_pct', 'ratio2_pct', 'ratio3_pct', 'ratio4_pct']].sum(axis=1)
        return stock_data

    def select_long_short_stocks(self, stock_data):
        lower_pct, upper_pct = self.params.percentiles
        sorted_data = stock_data.sort_values(by='quality_score', ascending=False)

        long_stocks = sorted_data.iloc[:int(len(sorted_data) * upper_pct / 100)]
        short_stocks = sorted_data.iloc[-int(len(sorted_data) * lower_pct / 100):]

        long_stocks['weight'] = long_stocks['market_cap']
```