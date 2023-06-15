<div align="center">
  <h1>What Does Individual Option Volatility Smirk Tell Us About Future Equity Returns?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1107464)

## Trading rules

- Utilize stocks with liquid options for investment
- Calculate skewness using difference between implied volatilities of OTM puts and ATM calls
    - OTM put: strike price to stock price ratio closest to 0.95 (but under)
    - ATM call: strike price to stock price ratio closest to 1
- Include only options with 10 to 60 days until expiration
- Compute weekly SKEW by averaging daily SKEW over one week
- Sort firms into quintiles based on previous week’s average skew (Tuesday close to Tuesday close)
    - Portfolio 1: lowest skew
    - Portfolio 5: highest skew
- Go long on Portfolio 1, short on Portfolio 5 (value-weighted portfolios)
- Rebalance portfolios weekly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 1996-2005
- **Annual Return:** 9.19%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.46
- **Annual Standard Deviation:** 11.4%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np

class OptionSkewnessStrategy(bt.Strategy):
    def __init__(self):
        self.liquid_options = self.get_liquid_options()

    def get_liquid_options(self):
        # Implement your logic to obtain liquid options data
        pass

    def get_skew(self, stock):
        options = self.liquid_options[stock]
        otm_puts = [opt for opt in options if opt.type == 'put' and 0.95 < opt.strike / stock.close[0] < 1]
        atm_calls = [opt for opt in options if opt.type == 'call' and 0.99 < opt.strike / stock.close[0] < 1.01]
        valid_options = [opt for opt in options if 10 <= opt.days_to_expiration <= 60]
        otm_puts = sorted(valid_options, key=lambda x: abs(x.strike / stock.close[0] - 0.95))
        atm_calls = sorted(valid_options, key=lambda x: abs(x.strike / stock.close[0] - 1))
        skew = atm_calls[0].implied_volatility - otm_puts[0].implied_volatility
        return skew

    def next(self):
        if self.datetime.weekday() == 1:  # Tuesday
            skews = {stock: self.get_skew(stock) for stock in self.getdatanames()}
            sorted_skews = sorted(skews.items(), key=lambda x: x[1])
            quintile_size = len(sorted_skews) // 5
            long_portfolio = sorted_skews[:quintile_size]
            short_portfolio = sorted_skews[-quintile_size:]

            # Rebalance long positions
            long_weight = 1 / len(long_portfolio)
            for stock, skew in long_portfolio:
                self.order_target_percent(stock, long_weight)

            # Rebalance short positions
            short_weight = -1 / len(short_portfolio)
            for stock, skew in short_portfolio:
                self.order_target_percent(stock, short_weight)

cerebro = bt.Cerebro()
# Add data feeds and set initial cash
cerebro.addstrategy(OptionSkewnessStrategy)
cerebro.run()
```