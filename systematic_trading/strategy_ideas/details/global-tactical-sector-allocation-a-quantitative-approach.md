<div align="center">
  <h1>Global Tactical Sector Allocation: A Quantitative Approach</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1742422)

## Trading rules

- Identify cyclical, defensive, and neutral sectors
- Calculate monthly unique sector scores (sum of three sub-scores)
    - Sub-score 1: 12-month momentum (4 points for strongest, 3 for second, etc.)
    - Sub-score 2: 1-month momentum (4 points for strongest, 3 for second, etc.)
    - Sub-score 3: Seasonality points
        - Cyclical: 4 points in winter, 0 points in summer
        - Defensive: 4 points in summer, 0 points in winter
        - Neutral: 2 points all year
- Rank sectors based on total score monthly
- Apply two decision rules for portfolio allocation:
    - Rule 1: Threshold scores for long/short positions (above 9 for long, below 3 for short)
    - Rule 2: Position termination (total score surpasses 6 for both long and short) to limit turnover

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1970-2008
- **Annual Return:** 12.9%
- **Maximum Drawdown:** -29.9%
- **Sharpe Ratio:** 0.52
- **Annual Standard Deviation:** 17%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class SeasonalMomentumStrategy(bt.Strategy):
    def __init__(self):
        self.sectors = {
            'cyclical': [],
            'defensive': [],
            'neutral': []
        }

    def next(self):
        current_month = self.datetime.date(0).month
        season = 'winter' if 11 <= current_month <= 4 else 'summer'
        scores = {}
        for sector, stocks in self.sectors.items():
            for stock in stocks:
                momentum_12m = stock.close[0] / stock.close[-252] - 1
                momentum_1m = stock.close[0] / stock.close[-21] - 1
                seasonality_points = {
                    'cyclical': 4 if season == 'winter' else 0,
                    'defensive': 4 if season == 'summer' else 0,
                    'neutral': 2
                }[sector]
                scores[stock] = (momentum_12m, momentum_1m, seasonality_points)
        ranked_scores = sorted(scores.items(), key=lambda x: sum(x[1]), reverse=True)
        for i, (stock, score) in enumerate(ranked_scores):
            total_score = sum(score)
            if total_score > 9:
                self.order_target_percent(stock, target=1 / len(self.sectors))
            elif total_score < 3:
                self.order_target_percent(stock, target=-1 / len(self.sectors))
            elif total_score > 6:
                self.order_target_percent(stock, target=0)

cerebro = bt.Cerebro()
cerebro.addstrategy(SeasonalMomentumStrategy)

data_path = 'path/to/your/data'
for sector, stocks in sectors.items():
    for stock in stocks:
        data = bt.feeds.GenericCSVData(
            dataname=data_path,
            dtformat=('%Y-%m-%d'),
            openinterest=-1,
            timeframe=bt.TimeFrame.Days
        )
        cerebro.adddata(data)

cerebro.broker.setcash(100000)
cerebro.run()
```

Please note that you need to replace ‘path/to/your/data’ with the actual path to your data file and also define the ‘sectors’ variable with appropriate stock symbols for each sector. The provided code assumes daily data, and you may need to adjust the number of bars for the momentum calculation based on your data.