<div align="center">
  <h1>Fundamental Strength and the 52-Week High Anchoring Effect</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3421545)

## Trading rules

- Focus on common stocks listed on NYSE, AMEX, and NASDAQ
- Exclude financial firms and stocks priced below $5
- Consider only the largest firms by size
- Calculate nearness to 52-week high as the ratio of closing price to highest daily closing price in the past 12 months
- Compute Piotroski’s FSCORE quarterly as a measure of fundamental strength
- Monthly, sort stocks into 15 portfolios based on nearness to 52-week high and FSCORE
    - Use quintile sorting for 52-week nearness
    - Categorize FSCORE into three groups: 0-3 (low), 4-6 (mid), 7-9 (high)
- Go long on stocks with high nearness and FSCORE rankings; short those with low rankings
- Hold positions for 6 months, with monthly sorting and overlapping portfolios
- Use equal weighting for portfolios

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1985-2015
- **Annual Return:** 12.68%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.6
- **Annual Standard Deviation:** 21.06%

## Python code

### Backtrader

```python
import backtrader as bt

class PiotroskiFScore(bt.Strategy):
    params = dict(
        min_price=5.0,
        hold_period=6,
    )

    def __init__(self):
        self.nearness_rank = dict()
        self.fscore_rank = dict()

    def next(self):
        # Get the month of the current bar
        current_month = self.data.datetime.date().month

        # Perform portfolio sorting monthly
        if self._last_month != current_month:
            self._last_month = current_month
            self.rank_stocks()

        # Update positions
        self.adjust_positions()

    def rank_stocks(self):
        self.nearness_rank.clear()
        self.fscore_rank.clear()

        # Rank stocks by nearness to 52-week high
        for d in self.datas:
            if d.close[0] >= self.params.min_price:
                nearness = d.close[0] / max(d.close.get(size=252))
                self.nearness_rank[d] = nearness

        # Compute Piotroski's FSCORE here (not provided, use external data)
        # Example: self.fscore_rank[d] = fscore_value

        # Sort stocks by nearness and FSCORE
        self.nearness_rank = {k: v for k, v in sorted(self.nearness_rank.items(), key=lambda item: item[1], reverse=True)}
        self.fscore_rank = {k: v for k, v in sorted(self.fscore_rank.items(), key=lambda item: item[1], reverse=True)}

    def adjust_positions(self):
        num_stocks = len(self.datas)
        quintile_size = num_stocks // 5
        fscore_threshold_low = 3
        fscore_threshold_high = 7

        for i, d in enumerate(self.datas):
            # Check if stock is in the top or bottom quintile by nearness
            in_top_quintile = i < quintile_size
            in_bottom_quintile = i >= num_stocks - quintile_size

            # Check if stock has high or low FSCORE
            has_high_fscore = self.fscore_rank[d] >= fscore_threshold_high
            has_low_fscore = self.fscore_rank[d] <= fscore_threshold_low

            # Update positions
            if in_top_quintile and has_high_fscore:
                self.order_target_percent(d, target=1.0 / num_stocks)
            elif in_bottom_quintile and has_low_fscore:
                self.order_target_percent(d, target=-1.0 / num_stocks)
            else:
                self.order_target_percent(d, target=0)

            # Hold positions for 6 months
            if self.bar_executed[d] and self.bar_executed[d] + self.params.hold_period <= len(d):
                self.order_target_percent(d, target=0)


if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PiotroskiFScore)

    # Add data feeds here
    # Example: cerebro.adddata(data_feed)

    cerebro.run()
```

Please note that you will need to provide external data for the Piotroski’s FSCORE since it’s not available directly in Backtrader. The above code assumes that you have this data available and properly computed.