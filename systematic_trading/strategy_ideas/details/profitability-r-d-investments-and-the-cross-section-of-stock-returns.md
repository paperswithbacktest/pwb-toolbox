<div align="center">
  <h1>Profitability, R&D Investments and the Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3178186)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ stocks with prices above $5
- Calculate “Ability” measure yearly for each firm
    - Measure firm’s effectiveness at converting R&D expenditures into sales growth
    - Use rolling firm-level regressions on sales growth with lagged R&D for 5 different lags
    - Average the five R&D regression coefficients to obtain “Ability”
- Create a long-short equity portfolio
    - Sort stocks into quintiles based on “Ability” and three tiers based on R&D expenditures (low 30%, middle 40%, high 30%)
    - Go long on stocks with high “Ability” (top quintile) and large R&D spending (top 30%)
    - Short stocks with low “Ability” (bottom quintile) and large R&D spending (top 30%)
- Portfolio is equally weighted and rebalanced yearly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1980-2009
- **Annual Return:** 10%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.33
- **Annual Standard Deviation:** 18.3%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class AbilityStrategy(bt.Strategy):
    def __init__(self):
        pass

    def next(self):
        pass

    def ability_measure(self, data):
        pass

    def rebalance_portfolio(self):
        pass

class NYSEAboveFive(bt.feeds.PandasData):
    lines = ('ability',)
    params = (
        ('datetime', None),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', -1),
        ('ability', -1),
    )

def preprocess_data(data):
    # Perform any required data preprocessing steps here
    return data

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    data = pd.read_csv('your_data_file.csv')
    data = preprocess_data(data)
    data_feed = NYSEAboveFive(dataname=data)
    cerebro.adddata(data_feed)
    cerebro.addstrategy(AbilityStrategy)
    cerebro.addsizer(bt.sizers.EqualWeight)
    cerebro.broker.set_cash(100000)
    cerebro.broker.setcommission(commission=0.001)

    print('Starting Portfolio Value:', cerebro.broker.getvalue())
    cerebro.run()
    print('Ending Portfolio Value:', cerebro.broker.getvalue())
```

Please note that this code is just a template to get you started, and you will need to fill in the `preprocess_data`, `ability_measure`, and `rebalance_portfolio` functions with the specific logic to calculate the “Ability” measure, preprocess the data, and rebalance the portfolio according to the trading rules provided. Additionally, you’ll need to have a dataset containing stock data with the required information (prices, R&D expenditures, sales growth) to run this code.