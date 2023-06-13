<div align="center">
  <h1>An Update of ‘Loosening Your Collar: Alternative Implementations of QQQ Collars’: Credit Crisis and Out-of-Sample Performance</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1507991)

## Trading rules

- Hold 100% position in a Nasdaq index (e.g., QQQ ETF)
- Write a 1-month call option each month
- Use call option premiums to buy 6-month put options
- Use three market signals to determine:
    - Initial call and put moneyness
    - Ratio of number of calls written to number of puts and QQQ shares purchased
- Market Signals:
    1. Momentum
        - Based on simple moving average (SMA) cross-over of the NASDAQ-100 index
        - Use three SMA combinations: 1/50, 5/150, and 1/200
        - Buy signal: widen collar; Sell signal: tighten collar
    2. Volatility
        - Use daily VIX close as an indicator of implied volatility levels
        - Sell 0.75 (1.25) calls per index position if previous day’s VIX close is more than 1 standard deviation above (below) its current moving average level
        - Use three MA combinations: 50, 150, and 250
    3. Macroeconomic Indicator
        - Based on the trend of initial unemployment claims and the state of the economy with respect to the business cycle
        - Use NBER’s Business Cycle Dating Committee announcements to identify the state of the business cycle
        - Use three MA lengths on weekly data about initial unemployment claims: 10, 30, and 40
        - In expansionary periods: rising unemployment claims lead to shifting collar towards ATM put and OTM call (increase both strike prices)
        - In contractionary periods: rising unemployment claims lead to shifting strike prices in the opposite direction
- Combine momentum, volatility, and macroeconomic signals
- Target initial percentage moneyness of the options is an integer between ATM and 5% OTM

## Statistics

- **Markets Traded:** Equities, options
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1999-2010
- **Annual Return:** 12.52%
- **Maximum Drawdown:** -21.5%
- **Sharpe Ratio:** 0.75
- **Annual Standard Deviation:** 11.34%

## Python code

### Backtrader

```python
import backtrader as bt
import math

class CollarStrategy(bt.Strategy):
    params = (
        ('sma_combinations', [(1, 50), (5, 150), (1, 200)]),
        ('ma_lengths', [50, 150, 250]),
        ('unemployment_ma_lengths', [10, 30, 40]),
        ('vix_lookback', 1),
        ('vix_stdev_threshold', 1)
    )

    def __init__(self):
        self.qqq = self.datas[0]
        self.vix = self.datas[1]
        self.unemployment = self.datas[2]
        self.business_cycle = self.datas[3]
        self.smas = {}
        for sma_combination in self.params.sma_combinations:
            short_period, long_period = sma_combination
            self.smas[sma_combination] = {
                'short': bt.indicators.SimpleMovingAverage(self.qqq.close, period=short_period),
                'long': bt.indicators.SimpleMovingAverage(self.qqq.close, period=long_period)
            }
        self.vix_mas = {}
        for ma_length in self.params.ma_lengths:
            self.vix_mas[ma_length] = bt.indicators.SimpleMovingAverage(self.vix.close, period=ma_length)
        self.unemployment_mas = {}
        for unemployment_ma_length in self.params.unemployment_ma_lengths:
            self.unemployment_mas[unemployment_ma_length] = bt.indicators.SimpleMovingAverage(self.unemployment, period=unemployment_ma_length)

    def next(self):
        # Calculate signals
        momentum_signal = self.calc_momentum_signal()
        volatility_signal = self.calc_volatility_signal()
        macroeconomic_signal = self.calc_macroeconomic_signal()

        # Combine signals and determine collar parameters
        target_moneyness, call_ratio = self.combine_signals(momentum_signal, volatility_signal, macroeconomic_signal)

        # Implement collar strategy
        self.execute_collar_strategy(target_moneyness, call_ratio)

    def calc_momentum_signal(self):
        # Implement momentum signal calculation
        pass

    def calc_volatility_signal(self):
        # Implement volatility signal calculation
        pass

    def calc_macroeconomic_signal(self):
        # Implement macroeconomic signal calculation
        pass

    def combine_signals(self, momentum_signal, volatility_signal, macroeconomic_signal):
        # Combine signals and determine collar parameters
        pass

    def execute_collar_strategy(self, target_moneyness, call_ratio):
        # Implement the collar strategy
        pass

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Add data feeds for QQQ, VIX, unemployment, and business cycle
    # ...
    cerebro.adddata(qqq_data)
    cerebro.adddata(vix_data)
    cerebro.adddata(unemployment_data)
    cerebro.adddata(business_cycle_data)

    cerebro.addstrategy(CollarStrategy)
    cerebro.run()
```

This is a skeleton of the CollarStrategy implementation in Backtrader. You’ll need to implement the methods for calculating signals, combining signals, and executing the collar strategy as per your requirements. Additionally, add data feeds for QQQ, VIX, unemployment, and business cycle as needed.