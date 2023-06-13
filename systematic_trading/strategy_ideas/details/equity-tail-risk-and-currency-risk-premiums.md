<div align="center">
  <h1>Equity Tail Risk and Currency Risk Premiums</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3399980)

## Trading rules

- Strategy only invests in currencies of developed markets
- To measure US tail risk, construct a zero-investment strategy that longs the CBOE PPut index and shorts the S&P 500 index
- US equity tail risk is defined as the log return of the above strategy
- Regression for each currency’s monthly excess return is estimated using a rolling window of 60 months (equation on page 15)
- Regression is dependent on the return of the S&P 500 index and the US equity tail risk factor (equation 7 on page 16)
- Each currency is sorted into five portfolios based on estimated tail betas
- Buy the portfolio with the lowest beta and sell the portfolio with the highest beta
- Strategy is equally-weighted and rebalanced monthly

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1989-2018
- **Annual Return:** 6.13
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.75
- **Annual Standard Deviation:** 8.12

## Python code

### Backtrader

```python
import backtrader as bt

class DevelopedMarketStrategy(bt.Strategy):

    def __init__(self):
        self.sp500 = self.datas[0] # Assume S&P 500 is the first data
        self.pput = self.datas[1] # Assume CBOE PPut index is the second data
        self.tail_risk_factor = bt.indicators.LogReturns(self.pput/self.sp500) # Calculate US equity tail risk factor

        self.regression_window = 60 # Set rolling window for regression to 60 months

        self.portfolio_count = 5 # Sort currencies into 5 portfolios based on estimated tail betas

        self.months_since_last_rebalance = 0 # Keep track of months since last rebalance

    def prenext(self):
        self.next() # Move to next time step

    def next(self):
        if self.data0.datetime.date().day != 1 or self.months_since_last_rebalance < 30:
            # If not the first day of the month, or less than 30 days since last rebalance, skip
            return

        self.months_since_last_rebalance = 0 # Reset months since last rebalance

        # Get monthly excess returns for each currency
        cur_rets = [bt.indicators.LogReturns(cur/USD) for cur in self.datas[2:]]

        # Generate regression beta coefficients for each currency
        betas = []
        for cur_ret in cur_rets:
            dependent = cur_ret - bt.indicators.RollingLinearRegression(cur_ret - self.tail_risk_factor, period=self.regression_window).slope
            independent = self.tail_risk_factor - bt.indicators.RollingLinearRegression(self.tail_risk_factor, period=self.regression_window).slope
            model = bt.indicators.RollingLinearRegression(dependent, period=self.regression_window).beta
            betas.append(model)

        # Sort currencies into portfolios based on betas
        cur_data = zip(self.datas[2:], betas)
        cur_data = sorted(cur_data, key=lambda x: x[1]) # Sort by betas
        cur_data = [cur_data[i:i+len(cur_data)//self.portfolio_count] for i in range(0, len(cur_data), len(cur_data)//self.portfolio_count)] # Group into portfolios

        # Buy low beta portfolio, sell high beta portfolio
        for i in range(self.portfolio_count):
            if i == 0:
                self.buy_percent(cur_data[i][0][0], 1/self.portfolio_count)
            else:
                self.sell_percent(cur_data[i][-1][0], 1/self.portfolio_count)

    def buy_percent(self, data, perc):
        self.order_target_percent(data, perc)

    def sell_percent(self, data, perc):
        self.order_target_percent(data, -perc)

    def on_monthend(self):
        self.months_since_last_rebalance += 1 # Increment month counter

cerebro = bt.Cerebro()
cerebro.broker.set_cash(1000000) # Set initial cash
# Add S&P 500 and PPut index data
cerebro.adddata(bt.feeds.YahooFinanceData(dataname='^GSPC', fromdate=datetime(2011, 1, 1), todate=datetime(2020, 12, 31)))
cerebro.adddata(bt.feeds.YahooFinanceData(dataname='PPUT', fromdate=datetime(2011, 1, 1), todate=datetime(2020, 12, 31)))
# Add currency data
for cur in ['AUD', 'CAD', 'CHF', 'EUR', 'GBP', 'HKD', 'JPY', 'NOK', 'NZD', 'SEK', 'SGD']:
    cerebro.adddata(bt.feeds.YahooFinanceData(dataname=f'{cur}=X', fromdate=datetime(2011, 1, 1), todate=datetime(2020, 12, 31)))
cerebro.addstrategy(DevelopedMarketStrategy)
cerebro.run()
```