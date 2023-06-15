<div align="center">
  <h1>US Sector Rotation with Five-Factor Fama-French Alphas</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2987819)

## Trading rules

- Investment universe consists of 10 Fama-French US sector portfolios
- 36 months of past data is used to estimate the first set of alphas using the FF5 model
- Long position is taken in all sector portfolios that have positive FF5 alpha for the 36 months rolling window ending in month t
- Position is rebalanced every month using the rolling window alpha of the previous 36 months
- Portfolio is equally weighted

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1967-2014
- **Annual Return:** 11.07%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.7
- **Annual Standard Deviation:** 15.83%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class FamaFrench(bt.Indicator):
    lines = ('FF5_alpha', 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA')

    def __init__(self):
        self.addminperiod(36)

    def next(self):
        ff_factors = pd.read_csv('FF_factors.csv', index_col=0, parse_dates=True)
        start_idx = max(0, len(ff_factors)-35)
        ff_factors = ff_factors.iloc[start_idx:]
        y = self.data.get(size=36) - ff_factors['RF'].values.mean()
        X = ff_factors.iloc[:, 1:]
        X = sm.add_constant(X)
        model = sm.OLS(y, X).fit()
        self.lines.FF5_alpha[0] = model.params['const']
        self.lines.Mkt-RF[0] = self.data[0] - ff_factors['RF'].values.mean()
        self.lines.SMB[0] = ff_factors['SMB'].mean()
        self.lines.HML[0] = ff_factors['HML'].mean()
        self.lines.RMW[0] = ff_factors['RMW'].mean()
        self.lines.CMA[0] = ff_factors['CMA'].mean()

class Universe(bt.Strategy):
    params = (
        ('n_months', 36),
    )

    def __init__(self):
        self.sectors = {}
        for sec in ['Beer', 'Hlth', 'Rtail', 'Clths', 'Hshld', 'Chems', 'Txtls', 'ElcEq', 'BusEq', 'Paper']:
            d = self.getdatabyname(sec)
            self.sectors[sec] = {
                'data': d,
                'FF5_alpha': FamaFrench(d).FF5_alpha,
            }
        self.weights = {sec: 0. for sec in self.sectors}

    def next(self):
        for sec, vals in self.sectors.items():
            if vals['FF5_alpha'][0] > 0:
                self.weights[sec] = 1.
            else:
                self.weights[sec] = 0.
        total_weight = sum(self.weights.values())
        if total_weight == 0:
            return
        for sec, weight in self.weights.items():
            self.order_target_percent(self.sectors[sec]['data'], target=weight/total_weight)

def run_strategy():
    cerebro = bt.Cerebro(stdstats=True)
    start_date = pd.to_datetime('1980-01-31')
    end_date = pd.to_datetime('2020-12-31')
    for sec in ['Beer', 'Hlth', 'Rtail', 'Clths', 'Hshld', 'Chems', 'Txtls', 'ElcEq', 'BusEq', 'Paper']:
        df = pd.read_csv(f'{sec}.csv', index_col=0, parse_dates=True)
        df = df.loc[start_date:end_date, ['PRC', 'RET']]
        df.columns = ['close', 'return']
        cerebro.adddata(bt.feeds.PandasData(dataname=df, plot=False), name=sec)

    cerebro.addstrategy(Universe)
    cerebro.run()
```