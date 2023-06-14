<div align="center">
  <h1>How to Time the Commodity Market</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=910907)

## Trading rules

- Investment universe includes S&P 500, copper, oil, and risk-free asset
- Non-commercial hedging pressure used for copper and oil, commercial and non-reportable hedging pressure used for S&P 500 as independent variable in regression equation
- Excess market return and volatilities of S&P 500, copper, and oil used as inputs for optimization calculation
- Optimization seeks portfolio with maximum Sharpe Ratio, calculated analytically or numerically
- Portfolio weights are used in immediate trading period
- Regression and optimization calculations done weekly, portfolio rebalanced accordingly
- Portfolio weights identified based on predicted asset return.

## Statistics

- **Markets Traded:** Commodities, equities
- **Period of Rebalancing:** Weekly
- **Backtest period:** 2000-2006
- **Annual Return:** 16.8%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.24
- **Annual Standard Deviation:** 10.3%

## Python code

### Backtrader

```python
# Define Investment universes
symbols = ['SPX', 'COPPER', 'OIL', 'RF']

# Define non-commercial hedging pressure for copper and oil
# Commercial and non-reportable hedging pressure for S&P 500 as independent variable for regression
copper_nc_hp = bt.feeds.GenericCSVData(dataname='copper_nc_hp.csv', dtformat=('%Y-%m-%d'), openinterest=-1)
oil_nc_hp = bt.feeds.GenericCSVData(dataname='oil_nc_hp.csv', dtformat=('%Y-%m-%d'), openinterest=-1)
spx_hedge_pressure = bt.feeds.GenericCSVData(dataname='spx_hedge_pressure.csv', dtformat=('%Y-%m-%d'), openinterest=-1)

# Define market return and volatilities for S&P 500, copper, and oil
market_returns_volatility = bt.feeds.GenericCSVData(dataname='market_returns_volatility.csv', dtformat=('%Y-%m-%d'), openinterest=-1)

# Define optimization parameters and objective
class Optimizer(bt.Strategy):
    params = (('opt_params', dict()),)

    def __init__(self):
        self.portfolio_weights = None

    def updateparams(self):
        opt = bt.minimize(self.optimizer_return, **self.p.opt_params)
        self.portfolio_weights = list(opt.x)

    def optimizer_return(self, vals):
        w = list(vals)
        ret = (w * returns_df).sum().sum() / len(returns_df)
        risk = np.sqrt(np.dot(w, np.dot(cov_df, w)))
        return -ret / risk

# Define portfolio and rebalancing
class Portfolio(bt.Strategy):
    def __init__(self):
        self.weights = None

    def next(self):
        if self.getpositionbyname('RF').size:  # In case position in RF needs to be closed
            self.order_target_percent('RF', 0.0)

        if self.weights is None:
            return

        for i, symbol in enumerate(symbols[:-1]):
            self.order_target_percent(symbol, self.weights[i])

        self.weights = None

cerebro = bt.Cerebro()
cerebro.addstrategy(Optimizer, opt_params=dict(method='SLSQP', bounds=[(0, 1)]*3, args=()))
cerebro.addstrategy(Portfolio)

# Load data and perform regression and optimization weekly
cerebro.adddata(copper_nc_hp, name='COPPER_NC_HP')
cerebro.adddata(oil_nc_hp, name='OIL_NC_HP')
cerebro.adddata(spx_hedge_pressure, name='SPX_HEDGE_PRESSURE')
cerebro.adddata(market_returns_volatility, name='MARKET_RETURNS_VOLATILITY')

cerebro.resampledata(copper_nc_hp, name='COPPER_NC_HP', timeframe=bt.TimeFrame.Weeks)
cerebro.resampledata(oil_nc_hp, name='OIL_NC_HP', timeframe=bt.TimeFrame.Weeks)
cerebro.resampledata(spx_hedge_pressure, name='SPX_HEDGE_PRESSURE', timeframe=bt.TimeFrame.Weeks)
cerebro.resampledata(market_returns_volatility, name='MARKET_RETURNS_VOLATILITY', timeframe=bt.TimeFrame.Weeks)

cerebro.run()
```