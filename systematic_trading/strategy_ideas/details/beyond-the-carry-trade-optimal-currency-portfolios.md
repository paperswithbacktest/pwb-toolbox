<div align="center">
  <h1>Beyond the Carry Trade: Optimal Currency Portfolios</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041460)

## Trading rules

- Investment universe: Currencies from Australia, Canada, Czech Republic, Denmark, Finland, Hungary, Japan, Mexico, New Zealand, Norway, Poland, South Korea, Sweden, Switzerland, UK, US, and Euro area.
- Optimization input variables:
    - Sign: 1 if foreign currency yields higher interest rate than USD, -1 if it yields less.
    - FD: Interest rate spread; forward discount standardized using cross-section mean and standard deviation.
    - MOM: Momentum; cumulative currency appreciation in last three months, cross-sectionally standardized.
    - REV: Long-term reversal; cumulative real currency appreciation in previous five years, cross-sectionally standardized (excluding most recent three months).
- Optimization process:
    - Estimate performance for next month as sum of monthly risk-free return in USD plus return on optimal currency portfolio.
    - Determine optimal currency portfolio weights based on currency characteristics (sign, fd, mom, rev) to maximize investor utility function: U = ((1 + rp)^(1-gamma))/(1-gamma), where rp is estimated portfolio performance and gamma is investor’s coefficient of relative risk aversion (set to constant 5).
- Out-of-sample strategy:
    - Use initial 240 months of sample for training and design optimal portfolios for next 12 months.
    - Re-estimate model every 12 months using expanding window of monthly data.

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1996-2010
- **Annual Return:** 33.54%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.4
- **Annual Standard Deviation:** 23.89%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
import pandas as pd
from scipy.optimize import minimize

class CurrencyTradingStrategy(bt.Strategy):
    params = ( ('gamma', 5), )

    def __init__(self):
        self.currency_list = [
            'AUD', 'CAD', 'CZK', 'DKK', 'EUR', 'FIM', 'HUF', 'JPY', 'MXN', 'NZD',
            'NOK', 'PLN', 'KRW', 'SEK', 'CHF', 'GBP', 'USD'
        ]
        self.data_dict = {currency: self.getdatabyname(currency) for currency in self.currency_list}
        self.training_months = 240
        self.retrain_freq = 12
        self.month_counter = 0

    def next(self):
        if self.month_counter % self.retrain_freq == 0:
            portfolio_weights = self.optimize_portfolio()
            self.rebalance(portfolio_weights)
        self.month_counter += 1

    def optimize_portfolio(self):
        def utility_function(weights, *args):
            rp = np.sum(weights * args[0])
            gamma = args[1]
            U = -((1 + rp) ** (1 - gamma)) / (1 - gamma)
            return U

        # Calculate currency characteristics and construct input variables
        sign, fd, mom, rev = self.calculate_currency_characteristics()

        # Estimate performance for next month
        performance = self.estimate_performance(sign, fd, mom, rev)

        # Determine optimal currency portfolio weights
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = [(0, 1) for _ in range(len(self.currency_list))]
        initial_weights = np.array([1 / len(self.currency_list)] * len(self.currency_list))

        result = minimize(
            utility_function, initial_weights, args=(performance, self.params.gamma),
            bounds=bounds, constraints=constraints
        )

        return result.x

    def calculate_currency_characteristics(self):
        # Calculate sign, fd, mom, rev for each currency based on historical data
        # (implementation depends on the data source and data structure used)
        return sign, fd, mom, rev

    def estimate_performance(self, sign, fd, mom, rev):
        # Estimate performance for next month based on currency characteristics
        # (implementation depends on the model used to combine currency characteristics)
        return performance

    def rebalance(self, portfolio_weights):
        for i, currency in enumerate(self.currency_list):
            self.order_target_percent(self.data_dict[currency], target=portfolio_weights[i])

class MyStrategyRunner(bt.Cerebro):
    def **init**(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_currency_data(self, currency_data):
        for currency, data in currency_data.items():
            self.adddata(data, name=currency)

    def run_strategy(self):
        self.addstrategy(CurrencyTradingStrategy)
        return self.run()

if __name__ == '__main__':
    # Load currency data (implementation depends on the data source and data structure used)
    currency_data = load_currency_data()

    cerebro = MyStrategyRunner()
    cerebro.add_currency_data(currency_data)
    cerebro.broker.setcash(1000000)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, riskfreerate=0.0)

    results = cerebro.run_strategy()
    sharpe_ratio = results[0].analyzers[0].get_analysis()['sharperatio']
    print(f'Sharpe Ratio: {sharpe_ratio}')
```