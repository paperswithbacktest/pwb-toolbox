<div align="center">
  <h1>Overnight Returns, Daytime Reversals, and Future Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3324880)

## Trading rules

- Investment universe: Common stocks on NYSE, AMEX, and NASDAQ (excluding financial and utility firms)
- Decompose daily stock returns into:
    - Overnight component (RETCO): Close-to-open return
    - Daytime component (RETOC): Open-to-close return
- Identify negative daytime reversals: Positive overnight return followed by a negative daytime return
- Calculate monthly frequency (NRit) of negative daytime reversals for each stock
- Determine abnormal frequency of negative daytime reversals (AB_NR): Scale NRit by 12-month average NRit
- Sort stocks into quintiles based on AB_NR
- Independently sort stocks into terciles by market capitalization (SIZE)
- For large stocks, long top AB_NR quintile and short bottom AB_NR quintile
- Strategy: Equally-weighted and rebalanced monthly

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1993-2017
- **Annual Return:** 5.28%
- **Maximum Drawdown:** None
- **Sharpe Ratio:** 0.82
- **Annual Standard Deviation:** 6.43%

## Python code

### Backtrader

```python
import backtrader as bt

class NegativeDaytimeReversal(bt.Strategy):
    def __init__(self):
        self.retco = self.data.close / self.data.close(-1) - 1
        self.retoc = self.data.close / self.data.open - 1

    def next(self):
        # Identifying negative daytime reversals
        negative_daytime_reversals = (self.retco > 0) & (self.retoc < 0)

        # Calculate monthly frequency (NRit) of negative daytime reversals for each stock
        nr = bt.ind.SumN(negative_daytime_reversals, period=20) / 20

        # Determine abnormal frequency of negative daytime reversals (AB_NR)
        ab_nr = nr / bt.ind.SMA(nr, period=240) - 1

        # Rank stocks based on AB_NR and SIZE
        ranks_ab_nr = self.rank_data(ab_nr)
        ranks_size = self.rank_data(self.data.market_cap)

        # Long top AB_NR quintile and short bottom AB_NR quintile for large stocks
        large_stocks = ranks_size > 2 / 3 * len(self.datas)
        long_positions = large_stocks & (ranks_ab_nr > 4 / 5 * len(self.datas))
        short_positions = large_stocks & (ranks_ab_nr < 1 / 5 * len(self.datas))

        # Update positions
        for i, d in enumerate(self.datas):
            position = self.getposition(d).size
            if long_positions[i] and position <= 0:
                self.order_target_percent(d, target=1 / len(self.datas))
            elif short_positions[i] and position >= 0:
                self.order_target_percent(d, target=-1 / len(self.datas))
            elif not long_positions[i] and not short_positions[i] and position != 0:
                self.close(d)

    def rank_data(self, indicator):
        return sorted(range(len(self.datas)), key=lambda i: indicator[i])

cerebro = bt.Cerebro()
# Add data feed and other configurations
cerebro.addstrategy(NegativeDaytimeReversal)
# Run the backtest
results = cerebro.run()
```

This code provides a basic implementation of the Negative Daytime Reversal trading strategy in Backtrader. Please note that you will need to add the data feeds and configure the Cerebro engine according to your specific requirements.