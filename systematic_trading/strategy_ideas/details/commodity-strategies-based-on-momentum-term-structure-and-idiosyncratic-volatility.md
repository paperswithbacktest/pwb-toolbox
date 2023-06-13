<div align="center">
  <h1>Commodity Strategies Based on Momentum, Term Structure and Idiosyncratic Volatility</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1971917)

## Trading rules

- Investment universe: 27 commodity futures (agriculture, energy, livestock, metals, random length lumber)
- Data source: Daily settlement prices from Datastream
- Ranking factors:
    - Past performance over the previous R months
    - Roll-yields over the previous R months
    - Idiosyncratic volatility over the previous R months
- Scoring:
    - Sum of scores for each ranking factor (max N for best, min 0 for worst)
- Portfolio construction:
    - Long top quintile (highest total score)
    - Short bottom quintile (lowest total score)
- Position weighting: Equal weight for each commodity
- Rebalancing: Monthly, based on updated rankings

## Statistics

- **Markets Traded:** Commodities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1985-2011
- **Annual Return:** 7.38%
- **Maximum Drawdown:** -23.57%
- **Sharpe Ratio:** 0.68
- **Annual Standard Deviation:** 10.79%

## Python code

### Backtrader

```python
import backtrader as bt

class CommodityFuturesStrategy(bt.Strategy):
    params = (
        ('lookback', 252),
        ('num_quintiles', 5),
    )

    def __init__(self):
        self.rankings = []

    def prenext(self):
        self.next()

    def next(self):
        # Get available data
        if len(self.data) < self.params.lookback:
            return

        # Calculate ranking factors
        past_performance = [d.close[-1] / d.close[-self.params.lookback] - 1 for d in self.datas]
        roll_yields = [d.close[-1] / d.close[-self.params.lookback] - 1 for d in self.datas]
        idio_vol = [bt.indicators.StdDev(d.close, period=self.params.lookback) for d in self.datas]

        # Calculate total score for each commodity
        scores = []
        for i in range(len(self.datas)):
            score = sum([
                past_performance[i],
                roll_yields[i],
                idio_vol[i][0]
            ])
            scores.append(score)

        # Rank commodities by total score
        self.rankings = list(sorted(range(len(scores)), key=lambda x: scores[x]))

        # Calculate quintile size
        quintile_size = len(self.datas) // self.params.num_quintiles

        # Go long on top quintile
        for i in self.rankings[-quintile_size:]:
            if self.position.size == 0:
                self.buy(data=self.datas[i], size=1)

        # Go short on bottom quintile
        for i in self.rankings[:quintile_size]:
            if self.position.size == 0:
                self.sell(data=self.datas[i], size=1)

    def stop(self):
        self.log(f"Ending Value: {self.broker.getvalue()}", doprint=True)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(CommodityFuturesStrategy)

    # Add commodity data feeds
    for commodity in ['agriculture', 'energy', 'livestock', 'metals', 'random_length_lumber']:
        data = bt.feeds.GenericCSVData(
            dataname=f'{commodity}_daily_data.csv',
            dtformat=('%Y-%m-%d'),
            openinterest=-1,
            timeframe=bt.TimeFrame.Days,
            compression=1,
        )
        cerebro.adddata(data)

    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.run()
```

This code provides a basic implementation of the given trading rules using the Backtrader library. You may need to customize this code according to your specific requirements or data sources.