<div align="center">
  <h1>Patent-to-Market Premium</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3285921)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ stocks with complete accounting and returns data
- Exclude financial firms (SIC 6000-6999), closed-end funds, trusts, ADRs, REITs, units of beneficial interest, and firms with negative book value of equity
- Include only firms with at least one granted patent
- Step 1: Estimate market value (MT) of a firm’s new granted patents using stock market reaction during the first 2 days after patent grant, following Kogan et al. (2017)
- Step 2: Recursively compute the firm’s cumulative market value of patents (CMPi,t) for each firm i in year t
- Calculate Patent-to-Market (PTM) ratio: CMP divided by firm’s market value (MV)
- Sort stocks into decile portfolios based on PTM ratios
- Go long on highest decile and short on lowest decile
- Implement a value-weighted strategy with yearly rebalancing

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Yearly
- **Backtest period:** 1965-2011
- **Annual Return:** 5.91%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.16
- **Annual Standard Deviation:** 11.7%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class PatentToMarketStrategy(bt.Strategy):
    def __init__(self):
        self.mt_values = {}
        self.patent_values = {}
        self.ptm_ratios = {}
        self.sorted_stocks = []

    def prenext(self):
        self.next()

    def next(self):
        self.calculate_mt_values()
        self.calculate_patent_values()  # Implement this method with patent data
        self.calculate_ptm_ratios()
        self.rank_stocks()
        long_stocks = self.sorted_stocks[-10:]
        short_stocks = self.sorted_stocks[:10]

        for data in self.datas:
            if data._name in long_stocks:
                self.order_target_percent(data, target=1.0 / len(long_stocks))
            elif data._name in short_stocks:
                self.order_target_percent(data, target=-1.0 / len(short_stocks))
            else:
                self.order_target_percent(data, target=0)

    def calculate_mt_values(self):
        for data in self.datas:
            ticker = data._name
            close_prices = data.close.get(size=2)
            mt_value = close_prices[0] - close_prices[-1]
            self.mt_values[ticker] = mt_value

    def calculate_patent_values(self):
        # Implement this method with patent data
        pass

    def calculate_ptm_ratios(self):
        for ticker, mt_value in self.mt_values.items():
            if ticker in self.patent_values:
                self.ptm_ratios[ticker] = self.patent_values[ticker] / mt_value

    def rank_stocks(self):
        self.sorted_stocks = sorted(self.ptm_ratios, key=self.ptm_ratios.get)

cerebro = bt.Cerebro()
# Add data feeds for stocks here, making sure to filter based on the investment universe criteria
# e.g., cerebro.adddata(feed)
cerebro.addstrategy(PatentToMarketStrategy)
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)

print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
cerebro.run()
print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Please note that this code is a starting point and requires additional work to incorporate patent data and filtering the investment universe based on the criteria provided. You may need to integrate this code with your existing backtesting framework and data feeds.