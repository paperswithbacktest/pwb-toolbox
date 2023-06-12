<div align="center">
  <h1>A Low-Risk Strategy Based on Higher Moments in Currency Markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2666223)

## Trading rules

- The investment universe consists of 20 currency pairs against USD
- Calculate multiple higher moments (4th, 6th, 8th, 10th, 20th, 30th, 40th, 50th, 60th, 70th, 80th, 90th, 100th) for each currency from daily data over the last month
- Compare those moments against the average moment over multiple horizons (12 months, 24 months, 36 months, 48 months, 60 months, all months from the beginning of the sample)
- Create 78 strategies – one strategy for each calculated moment and lookback period – sort currencies into quintiles, take long positions in currencies whose higher return moments are low relative to past levels and short positions in currencies whose higher return moments are high relative to past levels
- Use an adaptive approach, pick the strategy which had the highest average return over the last 3-months (out of the 78 strategies) and trade this strategy (holds long-short currency portfolio) over the following month
- Currencies in a portfolio are equally weighted
- Repeat the process every month.

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1989-2014
- **Annual Return:** 11.07
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.38
- **Annual Standard Deviation:** 8%

## Python code

### Backtrader

```python
# Import necessary libraries
import backtrader as bt
import pandas as pd
import numpy as np

# Define the investment universe and load the historical data for the last month
universe = ['USD/EUR', 'USD/JPY', 'USD/GBP', 'USD/CAD', 'USD/CHF', 'USD/AUD', 'USD/NZD', 'USD/HKD', 'USD/SGD', 'USD/SEK', 'USD/NOK', 'USD/DKK', 'USD/TRY', 'USD/MXN', 'USD/ZAR', 'USD/RUB', 'USD/KRW', 'USD/BRL', 'USD/INR', 'USD/CNY']
data = {}
for pair in universe:
    data[pair] = pd.read_csv(f'{pair}_Historical_Data.csv', index_col='Date', parse_dates=True)

# Define time horizons
horizons = [12, 24, 36, 48, 60, len(data[universe[0]])]

# Define higher moments to calculate
high_moments = [4, 6, 8, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# Calculate higher moments for each currency and each horizon
moments = {}
for pair in universe:
    moments[pair] = {}
    for horizon in horizons:
        prices = data[pair]['Close'].iloc[-(horizon*30):] # last month of data
        returns = prices.pct_change().dropna()
        moments[pair][horizon] = [np.mean(returns**n) for n in high_moments]

# Create strategies, pick the one with best recent performance
class MomentStrategy(bt.Strategy):
    params = dict(
        moment=high_moments,
        horizon=horizons
    )
    
    def __init__(self):
        self.moment_idx = high_moments.index(self.params.moment)
        self.horizon_idx = horizons.index(self.params.horizon)
        self.quintiles = pd.qcut(self.moments[self.params.pair][self.params.horizon], 5, labels=False) + 1
    
    def next(self):
        if self.quintiles <= 2:
            self.buy()
        elif self.quintiles >= 4:
            self.sell()
    
    def stop(self):
        returns = self.broker.get_value() / self.broker.startingcash - 1
        self.rets.append(returns)
    
    def start(self):
        self.rets = []
    
    def get_analysis(self):
        return dict(avg_return=np.mean(self.rets))
    
    def __repr__(self):
        return f'Moment Strategy - Moment {self.params.moment}, Horizon {self.params.horizon}'

all_strategies = []
for pair in universe:
    for moment in high_moments:
        for horizon in horizons:
            strategy = MomentStrategy(moment=moment, horizon=horizon, pair=pair)
            strategy.moments = moments
            all_strategies.append(strategy)

recent_returns = pd.Series([s.get_analysis()['avg_return'] for s in all_strategies], index=range(len(all_strategies)))
best_strategy_idx = recent_returns.nlargest(1).index[0]
best_strategy = all_strategies[best_strategy_idx]

# Create portfolio of equally-weighted currencies for the best strategy
class CurrencyPortfolio(bt.Strategy):
    params = {
        'strategy': best_strategy
    }
    
    def __init__(self):
        self.currencies = list(universe)
        self.weights = 1 / len(self.currencies)
    
    def next(self):
        for currency in self.currencies:
            position_size = self.weights * self.broker.get_cash() / self.data[currency].lines.close[0]
            self.order_target_size(data=self.getdatabyname(currency), size=position_size)
    
    def stop(self):
        self.rets = (self.broker.get_value() / self.broker.startingcash - 1) * 100
    
    def start(self):
        self.rets = 0
    
    def get_analysis(self):
        return dict(return_perc=self.rets)
    
    def __repr__(self):
        return f'Currency Portfolio - {best_strategy}'

# Backtest the currency portfolio
start_date = max([data[pair].index[0] for pair in universe])
end_date = min([data[pair].index[-1] for pair in universe])

cerebro = bt.Cerebro()

for pair in universe:
    cerebro.adddata(bt.feeds.PandasData(dataname=data[pair][['Open', 'High', 'Low', 'Close']]), name=pair)

cerebro.addstrategy(CurrencyPortfolio)
cerebro.broker.setcash(100000)
cerebro.broker.setcommission(0.001)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

backtest_result = cerebro.run()

# Analyze the portfolio performance
portfolio_rets = []
for res in backtest_result:
    if isinstance(res, CurrencyPortfolio):
        portfolio_rets.append(res.get_analysis()['return_perc'])

portfolio_rets = pd.Series(portfolio_rets, index=data[universe[0]][start_date:end_date].index[:-1])
monthly_returns = portfolio_rets.resample('M').sum()
best_month_idx = monthly_returns.nlargest(1).index[0]
best_month_return = monthly_returns[best_month_idx]

```