<div align="center">
  <h1>Technological Links and Predictable Returns</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3036241)

## Trading rules

- Investment universe includes stocks of firms with non-missing market equity and SIC classification code from CRSP, and non-negative book equity data at the end of previous fiscal year from COMPUSTAT
- Firms must have at least one patent granted in the rolling-window of past five years
- Excluded are financial firms with one-digit SIC codes of six and stocks that are priced below one dollar a share at the beginning of the holding period to reduce the impact of micro-cap stocks
- Technology-linked return (TECHRET) is measured as the average monthly return of technology-linked firms in the technology space, weighted by pairwise technology closeness
- Technology closeness (TECH) between firms is defined as the uncentered correlation between all pairs, counted for every firm i, and month t, based on the number of patents in USPTO technology class over the rolling past five years
- TECH acts as a weight in calculating the average stock return of technology-linked firms and is biased toward firms which are more technologically close to the focal firm.
- TECHRET for firm i and month t is defined as a sum for every i different from j of TECHij multiplied by RETj (past month return of technology-linked firm j) divided by sum of TECHij for every i different from j
- At the beginning of each month, sort all firms into deciles based on the return of their technology-linked portfolios in the previous month
- Long the top decile and short the bottom decile
- Portfolio is value-weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1963-2012
- **Annual Return:** 8.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.25
- **Annual Standard Deviation:** 18.17%

## Python code

### Backtrader

```python
import backtrader as bt

class MyStrategy(bt.Strategy):

    def __init__(self):
        # Filter stocks by market equity, SIC classification code, and book equity data
        compustat = self.datas[0].compustat # assuming COMPUSTAT data is added as the first data feed
        crsp = self.datas[1].crsp # assuming CRSP data is added as the second data feed
        self.universe = list(set(compustat & crsp)) # intersection of COMPUSTAT and CRSP
        self.universe = [s for s in self.universe if s.book_equity_data > 0] # non-negative book equity data
        self.universe = [s for s in self.universe if s.price_at_beginning_of_holding_period >= 1] # exclude stocks priced below $1 a share

        # Set up rolling-window patent filter
        self.patent_window = bt.indicators.PatentWindow(patent_class="TECH", years=5) # assuming patent data is added as an indicator

        # Set up technology-linked return
        self.techret = bt.indicators.TechnologyReturn(universe=self.universe, patent_class="TECH")

        # Set up decile filter
        self.decile = bt.indicators.Decile(universe=self.universe, period=1, techret=self.techret)

        # Set up value-weighted portfolio and rebalancing
        self.weights = {} # dict to hold weight for each stock
        self.rebalance_monthly = bt.timer.MonthBegin(0) # rebalance at the beginning of each month

    def next(self):
        if not self.rebalance_monthly:
            return

        # Calculate stock weights
        for i, s in enumerate(self.universe):
            if self.decile[i] == 10:
                self.weights[s] = s.market_cap / sum([x.market_cap for x in self.universe if self.decile[self.universe.index(x)] == 10])
            elif self.decile[i] == 1:
                self.weights[s] = -s.market_cap / sum([x.market_cap for x in self.universe if self.decile[self.universe.index(x)] == 1])
            else:
                self.weights[s] = 0

        # Place orders based on weights
        for s in self.universe:
            size = self.weights[s] * self.broker.get_cash() / s.close[0]
            self.order_target_size(s, size)

        # Reset weight dict
        self.weights = {}
```