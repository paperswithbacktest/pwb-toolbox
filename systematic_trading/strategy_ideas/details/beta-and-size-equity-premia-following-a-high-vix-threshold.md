<div align="center">
  <h1>Beta and Size Equity Premia following a High-VIX Threshold</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2845610)

## Trading rules

- Investment universe includes small-cap and large-cap stocks
- Two ways to build portfolio:
    - Invest in ETFs (go long small-cap equity ETF, go short large-cap equity ETF)
    - Invest directly in small-cap stocks (four smallest deciles), short large-cap stocks (highest market cap decile).
- High-risk month: month that ends with expected market volatility in top quintile compared to historical volatility
- One month after high-risk month, go long small-cap stocks and short large-cap stocks
- Hold portfolio for 12 months
- Timing indicator (monthly volatility compared to historical volatility) is checked on a monthly basis.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1990-2014
- **Annual Return:** 11.94%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.53
- **Annual Standard Deviation:** 14.96%

## Python code

### Backtrader

```python
# Import necessary libraries
import backtrader as bt

class PortfolioStrategy(bt.Strategy):

    def __init__(self):

        # Investment universe includes small-cap and large-cap stocks
        self.large_cap = self.datas[0]
        self.small_cap = self.datas[1]

        # Set up the 2 possible ways to build the portfolio
        self.go_long_etf = False
        self.go_direct = False

        # Check if we are in a high-risk month
        self.high_risk_month = False

        # One month after high-risk month, go long small-cap and short large-cap stocks
        self.go_long_small = False
        self.go_short_large = False

        # Hold portfolio for 12 months
        self.month_counter = 0

        # Timing indicator is checked on a monthly basis
        self.add_timer(bt.timer.MONTH_END)

    def log(self, txt, dt=None):
        """Logging function for this strategy"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def notify_timer(self, timer, when, *args, **kwargs):
        """
        Notify the user on monthly intervals
        """
        if self.datas[0].datetime.datetime().month != when.month:
            return

        # Check if we are in a high risk month
        if self.high_risk_month == False and risk_month():
            self.high_risk_month = True
            self.log("Entered high-risk month")

        # One month after high-risk month, go long small-cap and short large-cap stocks
        elif self.high_risk_month == True and not self.go_long_small:

            # Reset high-risk month flag
            self.high_risk_month = False

            # Start long/short positions
            self.go_long_small = True
            self.go_short_large = True
            self.log("Enter long small-cap and short large-cap positions")

        # Hold portfolio for 12 months
        if self.month_counter == 12 and (self.go_long_etf or self.go_direct):
            if self.go_long_etf:
                self.close(self.long_etf)
                self.close(self.short_etf)
            elif self.go_direct:
                self.close(self.long_small)
                self.close(self.short_large)
            self.go_long_etf = False
            self.go_direct = False
            self.log("Hold the portfolio for 12 months")
            self.month_counter = 0

        # Check timing indicator on a monthly basis
        if self.go_long_etf == False and self.go_direct == False:
            if timing_indicator() and not self.high_risk_month:

                # Invest in ETFs
                self.long_etf = self.buy(self.small_cap)
                self.short_etf = self.sell(self.large_cap)

                self.go_long_etf = True
                self.log("Invest in ETF long small-cap and short large-cap positions")

            elif not self.high_risk_month:

                # Invest directly in small-cap and large-cap stocks
                self.long_small = self.buy(smallest_deciles())
                self.short_large = self.short(highest_market_cap_decile())

                self.go_direct = True
                self.log("Invest directly in small-cap and short large-cap stocks")

        # Increment month counter
        self.month_counter += 1
```