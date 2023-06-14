<div align="center">
  <h1>Liquidity Style of Mutual Funds</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1789906)

## Trading rules

- Focus on small-cap equity mutual funds, as liquidity effect is most prominent in smaller companies
- Obtain end-of-year equity holdings for each fund using 13F filings or mutual fund data providers (e.g., Morningstar)
- Calculate the liquidity factor for each stock in each fund (based on stock’s turnover - number of shares traded divided by outstanding shares)
- Create a weighted average liquidity score for each fund (stock’s liquidity score multiplied by its weight in the fund)
- Go long on the top quintile of funds with the lowest liquidity composite score
- Rebalance the portfolio annually

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1996-2009
- **Annual Return:** 10.26%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.33
- **Annual Standard Deviation:** 18.7%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class LiquidityEffect(bt.Strategy):
    def __init__(self):
        self.small_cap_funds = self.get_small_cap_funds()

    def next(self):
        if self.datetime.date().month == 1 and self.datetime.date().day == 1:
            self.rebalance_portfolio()

    def get_small_cap_funds(self):
        # Retrieve small-cap equity mutual funds list from a data source
        return [...]

    def calculate_liquidity_score(self, fund):
        holdings = self.get_fund_holdings(fund)
        liquidity_scores = []
        for stock in holdings:
            turnover = stock["shares_traded"] / stock["outstanding_shares"]
            liquidity_scores.append(turnover * stock["weight"])
        return sum(liquidity_scores)

    def get_fund_holdings(self, fund):
        # Retrieve end-of-year equity holdings for the given fund from a data source
        return [...]

    def rebalance_portfolio(self):
        liquidity_scores = {}
        for fund in self.small_cap_funds:
            liquidity_scores[fund] = self.calculate_liquidity_score(fund)
        sorted_funds = sorted(liquidity_scores, key=liquidity_scores.get)
        top_quintile = sorted_funds[:len(sorted_funds) // 5]
        for fund in self.small_cap_funds:
            if fund in top_quintile:
                self.order_target_percent(fund, target=1 / len(top_quintile))
            else:
                self.order_target_percent(fund, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(LiquidityEffect)

    # Add small-cap equity mutual funds data to Cerebro
    small_cap_funds_data = [...]  # List of data feeds for small-cap funds

    for data in small_cap_funds_data:
        cerebro.adddata(data)

    cerebro.run()
```