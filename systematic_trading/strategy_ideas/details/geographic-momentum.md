<div align="center">
  <h1>Geographic Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1921537)

## Trading rules

- Investment universe: NYSE, AMEX, and NASDAQ listed stocks
- Obtain sales data from geographic segments through 10-Ks yearly
- Calculate “geographic return” using the weighted average of equity index returns in each region/country a company operates
- Weight for each country’s index return: (previous year’s sales from the country) / (total sales)
- Use MSCI Country Indexes (in USD) as proxy for country returns
- Long top 20% stocks and short bottom 20% stocks based on previous month’s geographic returns
- Rebalance portfolio monthly with equal weighting

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1998-2010
- **Annual Return:** 19.84%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.81
- **Annual Standard Deviation:** 19.56%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd

class GeographicMomentum(bt.Strategy):
    params = (
        ('top_percentile', 0.20),
        ('bottom_percentile', 0.20),
        ('rebalance_frequency', 21),  # Approximate number of trading days in a month
        ('msci_country_indexes', None),  # MSCI Country Indexes data in USD
        ('geographic_sales_data', None)  # Sales data from geographic segments, obtained through 10-Ks yearly
    )

    def __init__(self):
        self.inds = {}
        for d in self.datas:
            self.inds[d] = {}
            self.inds[d]['geographic_return'] = self.calculate_geographic_return(d)

    def calculate_geographic_return(self, data):
        stock_name = data._name
        stock_sales_data = self.params.geographic_sales_data[stock_name]
        total_sales = stock_sales_data['total_sales']
        geographic_return = 0
        for country, sales in stock_sales_data['country_sales'].items():
            country_weight = sales / total_sales
            country_index_return = self.params.msci_country_indexes[country]
            geographic_return += country_weight * country_index_return
        return geographic_return

    def rebalance(self):
        ranking = sorted(self.datas, key=lambda d: self.inds[d]['geographic_return'], reverse=True)
        num_stocks = len(ranking)
        top_cutoff = int(self.params.top_percentile * num_stocks)
        bottom_cutoff = int(self.params.bottom_percentile * num_stocks)
        for i, d in enumerate(ranking):
            if i < top_cutoff:
                self.order_target_percent(d, target=1 / top_cutoff)
            elif i >= num_stocks - bottom_cutoff:
                self.order_target_percent(d, target=-1 / bottom_cutoff)
            else:
                self.order_target_percent(d, target=0)

    def next(self):
        if self.datetime.date(0).day != 1:
            return
        if len(self) % self.params.rebalance_frequency == 0:
            self.rebalance()


# Add your data feeds and Cerebro setup here
```

Please note that this code snippet assumes you have properly preprocessed MSCI Country Indexes data and sales data from geographic segments (obtained through 10-Ks yearly) into the required format. You will also need to add your data feeds and configure the Cerebro engine according to your data sources and requirements.