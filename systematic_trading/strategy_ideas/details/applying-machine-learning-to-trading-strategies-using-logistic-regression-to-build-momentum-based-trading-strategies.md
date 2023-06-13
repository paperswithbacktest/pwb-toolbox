<div align="center">
  <h1>Applying Machine Learning to Trading Strategies: Using Logistic Regression to Build Momentum-Based Trading Strategies</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3325656)

## Trading rules

- Investment universe: SPX Index (traded via futures or ETFs)
- Input features:
    - Momentum (normalized to -1 to +1) over historical windows of 30, 60, 90, 120, 180, 270, 300, and 360 business days
    - Drawdowns (normalized to -1 to +1) over historical windows of 15, 60, 90, and 120 business days
- Predict profitability vector with daily values of 1 or 0, based on future profitability exceeding 5% annual threshold
- Use cubic polynomials for non-linear pattern identification from basic features
- Evaluate and combine features with weights daily
- Apply weighted factors as inputs to the sigmoid function (page 8)
- Minimize prediction error between actual future performance and sigmoid function prediction using historical data (cost function on page 9, regularization parameter set to 1)
- Make predictions three days ahead daily
- Stay in cash if return prediction doesn’t exceed minimum threshold, otherwise invest or remain invested in SPX at market close
- Rebalance strategy daily

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Daily
- **Backtest period:** 1964-2018
- **Annual Return:** 8.6%
- **Maximum Drawdown:** -45%
- **Sharpe Ratio:** 0.61
- **Annual Standard Deviation:** 14%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.preprocessing import MinMaxScaler

class LogisticMomentumStrategy(bt.Strategy):
    params = (
        ('momentum_periods', [30, 60, 90, 120, 180, 270, 300, 360]),
        ('drawdown_periods', [15, 60, 90, 120]),
        ('profitability_threshold', 0.05 / 252),
        ('prediction_days', 3),
    )

    def __init__(self):
        self.investment_universe = self.datas[0]
        self.momentum_indicators = [bt.indicators.Momentum(self.investment_universe.close, period=period) for period in self.params.momentum_periods]
        self.drawdown_indicators = [bt.indicators.DrawDown(self.investment_universe.close, period=period) for period in self.params.drawdown_periods]

    def next(self):
        current_day = len(self)
        if current_day < max(self.params.momentum_periods) + self.params.prediction_days:
            return

        X = []
        y = []

        for i in range(max(self.params.momentum_periods), current_day - self.params.prediction_days):
            features = []

            for momentum_indicator in self.momentum_indicators:
                features.append(momentum_indicator[-i])

            for drawdown_indicator in self.drawdown_indicators:
                features.append(drawdown_indicator[-i])

            X.append(features)
            y.append(1 if self.investment_universe.close[i + self.params.prediction_days] / self.investment_universe.close[i] - 1 > self.params.profitability_threshold else 0)

        X = MinMaxScaler(feature_range=(-1, 1)).fit_transform(X)
        poly = PolynomialFeatures(degree=3)
        X_poly = poly.fit_transform(X)

        model = LogisticRegression(C=1, random_state=0, solver='liblinear')
        model.fit(X_poly, y)

        current_features = [indicator[0] for indicator in self.momentum_indicators] + [indicator[0] for indicator in self.drawdown_indicators]
        current_features_normalized = MinMaxScaler(feature_range=(-1, 1)).fit_transform(np.array(current_features).reshape(1, -1))
        current_features_poly = poly.transform(current_features_normalized)
        prediction = model.predict_proba(current_features_poly)[:, 1]

        if prediction > self.params.profitability_threshold:
            self.order_target_percent(self.investment_universe, target=1)
        else:
            self.order_target_percent(self.investment_universe, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    data = bt.feeds.YahooFinanceData(
        dataname='^GSPC',
        fromdate=datetime.datetime(2000, 1, 1),
        todate=datetime.datetime(2021, 9, 30),
        buffered=True
    )

    cerebro.adddata(data)
    cerebro.addstrategy(LogisticMomentumStrategy)
    cerebro.broker.set_cash(10000)
    cerebro.run()
```

Please note that this code is just a starting point and might require further adjustments and optimization to work correctly with your specific setup and data. The code uses Backtrader and Scikit-learn libraries, so you need to have them installed to run the code.