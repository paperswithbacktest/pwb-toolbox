<div align="center">
  <h1>Predictable Dynamics in the Small Stock Premium</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2080404)

## Trading rules

- Create a Small-minus-Big factor portfolio using 6 Fama-French value-weighted portfolios formed on size and book-to-market
- Form the portfolios monthly as intersections of 2 portfolios formed on size and 3 portfolios formed on the ratio of book equity to market equity
- SMB is defined as the average return on the three small portfolios minus the average return on the three big portfolios
- A real-life portfolio can be created by trading two portfolios of stocks (long small caps and short, large caps) or more easily by a combination of two ETFs (tracking small and large-cap) of two futures contracts (S&P 500 and Russell 2000 as an example)
- Use the past 12-month return as a trading indicator
- Hold an SMB factor portfolio only if the past 12-month return were negative
- Rebalance the portfolio monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1927-2010
- **Annual Return:** 9.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.38
- **Annual Standard Deviation:** 14.62%

## Python code

### Backtrader

```python
import backtrader as bt

class FamaFrench(bt.Strategy):
    params = (
        ("size_dict", {"S": ["S1", "S2", "S3"], "B": ["B1", "B2", "B3"]}),
        ("beme_dict", {"L": ["L1", "L2", "L3"], "H": ["H1", "H2", "H3"]}),
    )

    def __init__(self):
        self.size_dict = self.params.size_dict
        self.beme_dict = self.params.beme_dict
        self.portfolio = {}
        self.weights = {}
        for size, size_portfolios in self.size_dict.items():
            for beme, beme_portfolios in self.beme_dict.items():
                for portfolio in size_portfolios:
                    if portfolio in beme_portfolios:
                        self.portfolio[portfolio] = bt.Security(self.data[portfolio])
                        self.weights[portfolio] = 0

    def next(self):
        if self.datas[0].datetime.date().month == self.datas[0].datetime.date().replace(day=1).month:
            for size, size_portfolios in self.size_dict.items():
                for beme, beme_portfolios in self.beme_dict.items():
                    portfolios_intersection = list(set(size_portfolios) & set(beme_portfolios))
                    if len(portfolios_intersection) == 2:
                        big_portfolio, small_portfolio = sorted(portfolios_intersection)[::-1]
                        long = self.portfolio[small_portfolio]
                        short = self.portfolio[big_portfolio]
                        long_return = long[-1] / long[-2] - 1  # Daily return
                        short_return = short[-1] / short[-2] - 1  # Daily return
                        long_weight = self.weights[small_portfolio] + long_return / 3
                        short_weight = self.weights[big_portfolio] + short_return / 3
                        self.weights[small_portfolio] = long_weight
                        self.weights[big_portfolio] = short_weight

            total_exposure = sum([abs(weight) for weight in self.weights.values()])
            for portfolio in self.portfolio.values():
                portfolio_weight = self.weights[portfolio._name]
                portfolio_exposure = portfolio_weight / total_exposure if total_exposure != 0 else 0
                portfolio.set_exposure(portfolio_exposure)

    def compute_return(self, portfolio):
        annual_return = portfolio[-1] / portfolio.buysell[0][0] ** (365.25 / len(portfolio)) - 1  # Annualized return
        return annual_return

    def should_hold(self):
        for size, size_portfolios in self.size_dict.items():
            for beme, beme_portfolios in self.beme_dict.items():
                portfolios_intersection = list(set(size_portfolios) & set(beme_portfolios))
                if len(portfolios_intersection) == 2:
                    big_portfolio, small_portfolio = sorted(portfolios_intersection)[::-1]
                    long = self.portfolio[small_portfolio]
                    long_return = self.compute_return(long)
                    if long_return >= 0:
                        self.weights[small_portfolio] = 0
                        self.weights[big_portfolio] = 0

    def rebalance_portfolio(self):
        for portfolio in self.portfolio.values():
            if portfolio.buysell:
                if (
                    self.datas[0].datetime.date().month
                    == self.datas[0].datetime.date().replace(day=1).month
                ):
                    if self.should_hold():
                        portfolio.sell()
                    else:
                        portfolio.buy()

cerebro = bt.Cerebro()

for ticker in TICKERS:
    data = bt.feeds.YahooFinanceData(
        dataname=ticker,
        fromdate=FROM_DATE,
        todate=TO_DATE,
        reverse=False
    )
    cerebro.adddata(data)

cerebro.addstrategy(FamaFrench,
                    size_dict={"S": ["S1", "S2", "S3"], "B": ["B1", "B2", "B3"]},
                    beme_dict={"L": ["L1", "L2", "L3"], "H": ["H1", "H2", "H3"]})

cerebro.run()
```