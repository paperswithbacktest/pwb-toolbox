<div align="center">
  <h1>Trend-Following Strategies for Tail-Risk Hedging and Alpha Generation</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167787)

## Trading rules

- Investment universe: 32 country equity markets (developed and emerging markets)
- Momentum calculation: Based on past 12-month performance for each market
- Quartile formation: Q1 (lowest momentum) to Q4 (highest momentum)
- Long position: Invest in highest momentum quartile countries if above 10-month moving average
- Cash position: If a country is not above 10-month moving average, hold cash instead of equity
- Portfolio weighting: Equally weighted (12.5% fixed position per country)
- Rebalancing: Monthly
- Allocation example: 50% equities (split among 4 upward trending markets), 50% cash (if only 4 out of 8 markets are trending higher)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1970-2008
- **Annual Return:** 20.59%
- **Maximum Drawdown:** -20.07%
- **Sharpe Ratio:** 0.94
- **Annual Standard Deviation:** 17.64%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class MomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 12),
        ('moving_average_period', 10),
        ('num_positions', 8),
        ('percent_per_position', 12.5),
    )

    def __init__(self):
        self.momentum = {data: bt.indicators.RateOfChange(data.close, period=self.params.momentum_period) for data in self.datas}
        self.moving_average = {data: bt.indicators.SimpleMovingAverage(data.close, period=self.params.moving_average_period) for data in self.datas}

    def next(self):
        ranks = list(self.datas)
        ranks.sort(key=lambda data: self.momentum[data][0], reverse=True)
        num_stocks_to_buy = int(self.params.num_positions / 2)
        selected_stocks = ranks[:num_stocks_to_buy]

        for data in selected_stocks:
            if data.close[0] > self.moving_average[data][0]:
                self.order_target_percent(data, target=self.params.percent_per_position / 100)

        for data in self.datas:
            if data not in selected_stocks:
                self.order_target_percent(data, target=0)

class CountryEquityIndex(bt.feeds.PandasData):
    pass

cerebro = bt.Cerebro()

# Load data for the 32 country equity markets
for market in equity_markets:
    data = CountryEquityIndex(dataname=pd.read_csv(market, parse_dates=True, index_col='Date'))
    cerebro.adddata(data)

cerebro.addstrategy(MomentumStrategy)
cerebro.broker.setcash(100000.0)
results = cerebro.run()
```

Replace `equity_markets` with a list of your data file paths for the 32 country equity markets. This code uses the Backtrader library to implement the trading rules you provided.