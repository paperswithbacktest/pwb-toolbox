<div align="center">
  <h1>The Baltic Dry Index as a Predictor of Global Stock Returns, Commodity Returns, and Global Economic Activity</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1747345)

## Trading rules

- Allocate portfolio between emerging market stocks and risk-free bonds (cash)
- Utilize CRRA utility function with gamma set to 3: U= (X^(1-gamma)) / (1-gamma)
- Use BDI index history as independent variable in regression equation to predict next period’s equity returns
- Begin with initial sample length of 120 months, expanding independent variable’s sample monthly
- Maximize investor’s utility for the next period using regression equation information
- Adjust stock and cash weights in the portfolio accordingly
- Rebalance portfolio on a monthly basis

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1988-2010
- **Annual Return:** 10.23%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.6
- **Annual Standard Deviation:** 10.4%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LinearRegression

class BDIStockMarketTiming(bt.Strategy):
    params = dict(
        gamma=3,  # Utility function parameter
        sample_length=120,  # Length of the historical sample for regression
        rebalance_days=30  # Rebalance frequency in days
    )

    def __init__(self):
        self.bdi = self.datas[1]  # Baltic Dry Index data
        self.days_since_rebalance = 0  # Counter for rebalance frequency
        self.equity_returns = []  # List to store equity returns
        self.bdi_history = []  # List to store BDI values

    def next(self):
        self.days_since_rebalance += 1
        self.equity_returns.append(self.data.close[0] / self.data.close[-1] - 1)
        self.bdi_history.append(self.bdi[0])

        if len(self.equity_returns) < self.params.sample_length:
            return

        if self.days_since_rebalance >= self.params.rebalance_days:
            self.days_since_rebalance = 0

            X = np.array(self.bdi_history[-self.params.sample_length:]).reshape(-1, 1)
            y = np.array(self.equity_returns[-self.params.sample_length:])

            model = LinearRegression().fit(X, y)
            predicted_return = model.predict(np.array([self.bdi[0]]).reshape(-1, 1))[0]

            utility_func = lambda x: (x**(1 - self.params.gamma)) / (1 - self.params.gamma)
            stock_weight = utility_func(predicted_return)

            self.order_target_percent(self.data, stock_weight)  # Allocate stock weight
            self.order_target_percent(self.datas[2], 1 - stock_weight)  # Allocate remaining to risk-free bonds

cerebro = bt.Cerebro()

data0 = bt.feeds.YourEmergingMarketStockDataFeed()  # Replace with your own stock data feed
data1 = bt.feeds.YourBDIDataFeed()  # Replace with your own BDI data feed
data2 = bt.feeds.YourRiskFreeBondsDataFeed()  # Replace with your own risk-free bonds data feed

cerebro.adddata(data0)
cerebro.adddata(data1)
cerebro.adddata(data2)

cerebro.addstrategy(BDIStockMarketTiming)

results = cerebro.run()
```

Make sure to replace `YourEmergingMarketStockDataFeed`, `YourBDIDataFeed`, and `YourRiskFreeBondsDataFeed` with the appropriate data feeds for your backtesting environment. This code assumes you have already set up Backtrader and have the necessary data feeds.