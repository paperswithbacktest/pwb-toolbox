<div align="center">
  <h1>Learning to Love Investment Bubbles: What if Sir Isaac Newton had been a Trendfollower?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1923387)

## Trading rules

- 20 futures markets are included in the investment universe
- Initial position size is based on the maximum amount of risk the investor is willing to take for each position
- Maximum risk is 2% of equity in each position
- Exposure of each position is restricted to 10% of current equity
- Donchian Channel Breakout 100 strategy is used
- The Donchian channel is formed by taking the highest high and the lowest low of the last 100 periods
- The investor goes long/short at Stop as soon as the price crosses the upper/lower Donchian band of 100 days
- The investor exits and reverses position as soon as the opposite Donchian band is crossed
- Four times the ATR of 10 days is used as a parameter for the maximum risk to calculate the position size
- Position sizing is 2% based on the initial stop loss (based on four times the 10-day-ATR)

## Statistics

- **Markets Traded:** Bonds, commodities, currencies, equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1990-2004
- **Annual Return:** 21.24%
- **Maximum Drawdown:** -32.74%
- **Sharpe Ratio:** 0.88
- **Annual Standard Deviation:** 24.14%

## Python code

### Backtrader

```python
import backtrader as bt

class DonchianChannelBreakout(bt.Strategy):

    params = (
        ('period', 100),
        ('atr_period', 10),
        ('risk_per_trade', 0.02),
    )

    def __init__(self):

        self.atr = bt.indicators.ATR(period=self.params.atr_period)

        self.high_channel = bt.indicators.Highest(self.data.high(-1), period=self.params.period)
        self.low_channel = bt.indicators.Lowest(self.data.low(-1), period=self.params.period)

        self.size = None  # Number of shares to buy/sell

    def next(self):

        if self.size:  # Check if we have open position
            return

        # Calculate initial stop loss
        atr_value = self.atr[0]
        stop_loss = atr_value * 4

        # Calculate how many shares to buy/sell
        risk_per_share = stop_loss * self.params.risk_per_trade
        max_exposure = self.broker.get_value() * 0.1
        shares = int(max_exposure / risk_per_share)

        # Check if we have enough money to open the position
        if shares * self.data.close < self.broker.get_cash():
            if self.data.close > self.high_channel[0]:
                self.size = shares
                self.sell(size=self.size)

            elif self.data.close < self.low_channel[0]:
                self.size = shares
                self.buy(size=self.size)

        # Reverse position if opposite channel is crossed
        elif self.size > 0 and self.data.close < self.low_channel[0]:
            self.close()
            self.size = -shares
            self.buy(size=self.size)

        elif self.size < 0 and self.data.close > self.high_channel[0]:
            self.close()
            self.size = shares
            self.sell(size=self.size)
```