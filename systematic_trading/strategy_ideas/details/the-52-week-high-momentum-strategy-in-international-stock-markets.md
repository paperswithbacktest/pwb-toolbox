<div align="center">
  <h1>The 52-Week High Momentum Strategy in International Stock Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1364566)

## Trading rules

- Investment Universe: NYSE, AMEX, and NASDAQ stocks (CRSP database utilized for backtesting)
- Calculate PRILAG i,t: Price i,t / 52-Week High i,t for each stock at month-end
- Compute Weighted Average PRILAG i,t: Determine weighted average of PRILAG i,t for all firms within each industry (20 industries total) using market capitalization as weight
- Identify Winner and Loser Industries: Select six industries with highest (winners) and lowest (losers) weighted averages of PRILAG i,t
- Create Portfolios: Long winner stocks and short loser stocks, holding positions for three months
- Portfolio Weighting: Assign equal weights to stocks in each portfolio
- Rebalance Monthly: Rebalance 1/3 of the portfolio every month

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1963-2009
- **Annual Return:** 11.75%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.7
- **Annual Standard Deviation:** 11%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class PRILAGStrategy(bt.Strategy):
    params = (
        ('holding_period', 3), 
        ('num_industries', 20), 
        ('num_winners', 6), 
        ('num_losers', 6), 
    )

    def __init__(self):
        self.prilag = {}
        self.stock_industry = {}
        self.industry_weighted_prilag = {industry: 0 for industry in range(self.p.num_industries)}

    def next(self):
        if self.datetime.date().day != 1:
            return

        self.update_prilag()

        if len(self) % self.p.holding_period == 0:
            self.update_industry_weighted_prilag()
            self.rebalance_portfolio()

    def update_prilag(self):
        for stock in self.datas:
            self.prilag[stock] = stock.close[0] / stock.high.get(size=252)

    def update_industry_weighted_prilag(self):
        industry_prilag_sum = {industry: 0 for industry in range(self.p.num_industries)}
        industry_marketcap_sum = {industry: 0 for industry in range(self.p.num_industries)}

        for stock in self.datas:
            industry = self.stock_industry[stock]
            market_cap = stock.close[0] * stock.volume[0]

            industry_prilag_sum[industry] += self.prilag[stock] * market_cap
            industry_marketcap_sum[industry] += market_cap

        for industry in range(self.p.num_industries):
            self.industry_weighted_prilag[industry] = industry_prilag_sum[industry] / industry_marketcap_sum[industry]

    def rebalance_portfolio(self):
        sorted_industries = sorted(self.industry_weighted_prilag, key=self.industry_weighted_prilag.get)
        winners = sorted_industries[-self.p.num_winners:]
        losers = sorted_industries[:self.p.num_losers]

        for stock in self.datas:
            industry = self.stock_industry[stock]
            stock_weight = 1 / len(self.datas)
            if industry in winners:
                self.order_target_percent(stock, target=stock_weight)
            elif industry in losers:
                self.order_target_percent(stock, target=-stock_weight)
            else:
                self.order_target_percent(stock, target=0)

    def load_stock_data(stock_symbols, industry_map):
        data_feed = []
        for symbol in stock_symbols:
            data = bt.feeds.PandasData(dataname=pd.read_csv(f'{symbol}.csv', parse_dates=['Date'], index_col='Date'))
            data_feed.append(data)
            strategy.stock_industry[data] = industry_map[symbol]
        return data_feed

cerebro = bt.Cerebro()
cerebro.addstrategy(PRILAGStrategy)

stock_symbols = ['AAPL', 'GOOG', 'TSLA', 'AMZN', 'MSFT', 'FB']
industry_map = {'AAPL': 0, 'GOOG': 1, 'TSLA': 2, 'AMZN': 0, 'MSFT': 1, 'FB': 2}

data_feed = load_stock_data(stock_symbols, industry_map)

for data in data_feed:
    cerebro.adddata(data)

cerebro.broker.setcash(100000)
cerebro.broker.setcommission(commission=0.001)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
cerebro.addanalyzer(bt.analyzers.DrawDown)