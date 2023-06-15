<div align="center">
  <h1>When Low Beats High: Riding the Sales Seasonality Premium</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3174181)

## Trading rules

- Investment universe: Non-financial U.S. stocks listed on NYSE, AMEX, or NASDAQ from CRSP files (excluding shares codes 10 and 11)
- Construct quarterly variable SEA[q,t]: SALES[q,t] / ANNUALSALES[t]
- Calculate AVGSEA[q,t]: Average of SEA[q,t] over years t-2 and t-3 (mitigate outlier impact)
- Monthly stock allocation: Sort into deciles based on ex-ante sales seasonality measure (AVGSEA[q,t] in year t-2)
- Portfolio strategy: Long lowest decile, short highest decile
- Portfolio management: Value-weighted, held for one month, rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1970-2016
- **Annual Return:** 8.73%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.38
- **Annual Standard Deviation:** 12.35%

## Python code

### Backtrader

Here’s a basic Backtrader Python code snippet for implementing the given trading rules:

```python
import backtrader as bt

class SalesSeasonality(bt.Strategy):
    def __init__(self):
        self.sea = {}      # Dictionary to store sales seasonality
        self.avgsea = {}   # Dictionary to store average sales seasonality

    def prenext(self):
        self.next()

    def next(self):
        for data in self.datas:
            symbol = data._name
            if symbol not in self.sea:
                self.sea[symbol] = []
            if symbol not in self.avgsea:
                self.avgsea[symbol] = []

            sales = data.sales[0]                # Get current sales value
            annual_sales = data.annualsales[0]   # Get annual sales value
            sea = sales / annual_sales           # Calculate sales seasonality

            self.sea[symbol].append(sea)         # Append sales seasonality to the dictionary

            if len(self.sea[symbol]) >= 8:
                avgsea = sum(self.sea[symbol][-8:-4]) / 4   # Calculate average sales seasonality
                self.avgsea[symbol].append(avgsea)           # Append average sales seasonality to the dictionary

        if len(self.avgsea) > 0:
            sorted_symbols = sorted(self.avgsea, key=lambda x: self.avgsea[x][-1], reverse=True)
            long_symbols = sorted_symbols[:len(sorted_symbols)//10]    # Select top 10% symbols with highest average sales seasonality
            short_symbols = sorted_symbols[-len(sorted_symbols)//10:]  # Select bottom 10% symbols with lowest average sales seasonality

            for data in self.datas:
                symbol = data._name
                if symbol in long_symbols:
                    self.order_target_percent(data, target=1 / len(long_symbols))    # Allocate equal weights to long symbols
                elif symbol in short_symbols:
                    self.order_target_percent(data, target=-1 / len(short_symbols))  # Allocate equal weights to short symbols
                else:
                    self.order_target_percent(data, target=0.0)    # No position for other symbols

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SalesSeasonality)

    # Load your data feed
    # data = btfeeds.PandasData(dataname=your_dataframe)
    # cerebro.adddata(data)

    cerebro.broker.set_cash(100000)
    cerebro.run()

    print(f"Final Portfolio Value: {cerebro.broker.getvalue()}")
```

Replace the ‘your_dataframe’ with your custom data containing columns for sales and annualsales. This code snippet is a starting point and may need some adjustments depending on the data format and other factors.