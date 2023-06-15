<div align="center">
  <h1>Term Structure of Credit Default Swap Spreads and Cross-Section of Stock Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1735162)

## Trading rules

- Investment universe: NYSE, AMEX and NASDAQ stocks with liquid CDS contracts
- Slope of CDS term structure is measured by the difference between 5-year CDS spread and 1-year CDS spread
- Monthly sorting of stocks into deciles based on previous month’s ending CDS slope
- Short position on stocks with highest CDS slopes
- Long position on stocks with lowest CDS slopes
- Portfolio is rebalanced monthly
- Stocks are equally weighted

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 2002-2009
- **Annual Return:** 27.57%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.99
- **Annual Standard Deviation:** 23.84%

## Python code

### Backtrader

```python
import backtrader as bt

class CdsSlopeStrategy(bt.Strategy):
    def __init__(self):
        # Set investment universe to NYSE, AMEX, and NASDAQ stocks with liquid CDS contracts
        self.filter = bt.filters.FilterEquities(
            numstocks=None,
            criteria=bt.filters.StockFilters.US_Stocks()
            & bt.filters.StockFilters.HasCDS(contract_type='vanilla')
        )

        # Define CDS term structure and create slope indicator
        cds_1y = self.datas[0].closes
        cds_5y = self.datas[1].closes
        cds_slope = cds_5y / cds_1y - 1

        # Monthly sorting of stocks based on previous month's ending CDS slope
        self.add_timer(
            when=bt.Timer.SESSION_START,
            monthdays=[1],
            monthcarry=True
        )

        # Moving average of CDS slope
        self.retslopemean = bt.indicators.MovingAverage(
            cds_slope,
            period=21
        )

        # Set up long and short positions based on CDS slope
        self.long = bt.indicators.Rank(cds_slope) <= 1
        self.short = bt.indicators.Rank(cds_slope) >= (self.filter.numstocks // 2)

    def next(self):
        # Get long and short positions based on CDS slope
        longs = self.long
        shorts = self.short

        # Equally weight long and short positions
        long_pos_size = self.broker.get_cash() / len(longs)
        short_pos_size = -self.broker.get_cash() / len(shorts)

        # Place orders for long and short portfolios
        for i, d in enumerate(self.datas):
            if longs[i]:
                self.buy(d, size=long_pos_size)
            elif shorts[i]:
                self.sell(d, size=short_pos_size)

    def notify_timer(self, timer, when, *args, **kwargs):
        if when[1] == 1:
            # Rebalance positions monthly
            self.rebalance_portfolio()

    def rebalance_portfolio(self):
        # Calculate equally weighted position size
        pos_size = self.broker.get_value() / len(self.datas)

        # Close out all positions
        for i, d in enumerate(self.datas):
            self.close(d)

        # Reorder positions
        self.order_target_percent(target=pos_size, selectfilter=self.filter)
```