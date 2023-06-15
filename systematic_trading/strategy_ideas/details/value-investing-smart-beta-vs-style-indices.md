<div align="center">
  <h1>Value Investing: Smart Beta vs. Style Indices</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2477293)

## Trading rules

- Investment universe only contains top 20% biggest companies (based on market capitalization) on NYSE, AMEX, and NASDAQ.
- Quintile portfolios are then formed based on the Book-to-Market ratio.
- Highest quintile based on Book-to-Market ratio is held for one year.
- Portfolio is weighted based on market capitalization.
- Portfolio is rebalanced after one year.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1927-2010
- **Annual Return:** 11.34%
- **Maximum Drawdown:** -81.98%
- **Sharpe Ratio:** 0.28
- **Annual Standard Deviation:** 20.10%

## Python code

### Backtrader

```python
# assume universe_df has columns ['asset', 'marketcap', 'exchange', 'book_to_market']
# include necessary imports
import backtrader as bt
import pandas as pd

class Top20HighestMarketCap(bt.Algo):
    def __init__(self, universe_df):
        self.top20 = universe_df.sort_values('marketcap', ascending=False)[:int(len(universe_df)*0.2)]['asset']

    def __call__(self, target):
        if target._name in self.top20:
            return True
        else:
            return False

class BookToMarketQuintilePortfolio(bt.Algo):
    def __init__(self, universe_df):
        self.quintiles = universe_df.groupby('exchange')['book_to_market'].transform(lambda x: pd.qcut(x, 5, labels=False))

    def __call__(self, target):
        if target.book_to_market >= 4: # highest quintile
            return True
        else:
            return False

class MarketCapWeighted(bt.Algo):
    def __init__(self, universe_df):
        self.weights = universe_df['marketcap']/universe_df['marketcap'].sum()

    def __call__(self, target):
        return self.weights[target._name]

# assume cerebro has been created and data has already been added
universe_df = pd.DataFrame({'asset': [d._name for d in cerebro.datas],
                            'marketcap': [d.lines[0][-1] for d in cerebro.datas],
                            'exchange': [d._name.split('-')[0] for d in cerebro.datas],
                            'book_to_market': [d.lines[1][-1] for d in cerebro.datas]})
cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)
cerebro.addsizer(MarketCapWeighted(universe_df))
cerebro.addstrategy(bt.Strategy)
cerebro.broker.setcommission(commission=0.001)
cerebro.broker.setcash(100000)

# define trading rules
cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years, _name='TimeReturn_1yr')
cerebro.addanalyzer(bt.analyzers.SharpeRatio_Annual, timeframe=bt.TimeFrame.Years, _name='SharpeRatio_1yr')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='DrawDown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='Returns')
cerebro.addanalyzer(bt.analyzers.Transactions, _name='Transactions')
cerebro.addobserver(bt.observers.Value)
cerebro.addobserver(bt.observers.DrawDown)

cerebro.addanalyzer(bt.analyzers.AnnualReturn, timeframe=bt.TimeFrame.Years)
cerebro.addanalyzer(bt.analyzers.Calmar, timeframe=bt.TimeFrame.Years)

cerebro.addanalyzer(bt.analyzers.PositionsValue, _name='PositionsValue')

# define which stocks to select based on market cap
cerebro.addfi(Top20HighestMarketCap(universe_df))

# define quintile strategies
cerebro.addfi(BookToMarketQuintilePortfolio(universe_df))

# run backtest
cerebro.run()

# print out analysis results
print('Annual Return:', cerebro.analyzers.getbyname('AnnualReturn').get_analysis())
print('Drawdown:', cerebro.analyzers.getbyname('Drawdown').get_analysis())
print('Sharpe Ratio:', cerebro.analyzers.getbyname('SharpeRatio_Annual').get_analysis())
print('Calmar Ratio:', cerebro.analyzers.getbyname('Calmar').get_analysis())
```