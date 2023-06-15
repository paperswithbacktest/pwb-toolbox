<div align="center">
  <h1>The Rehabilitation of Glidepath Investing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3347183)

## Trading rules

- Use stocks, funds, or ETFs as investment vehicles
- Choose two negatively correlated investment vehicles (e.g., VFINX and VUSTX)
- Look at the performance of the two funds over the prior quarter (the ranking period)
- Buy the fund with the higher return during the ranking period
- Hold the position for one quarter (the investment period)
- At the end of the investment period, repeat the cycle

## Statistics

- **Markets Traded:** Bonds, equities
- **Period of Rebalancing:** Quarterly
- **Backtest period:** 1991-2011
- **Annual Return:** 11.3%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.78
- **Annual Standard Deviation:** 9.3%

## Python code

### Backtrader

```python
import backtrader as bt
import datetime

class MomentumRanking(bt.Strategy):
    params = (
        ('ranking_period', 63),  # 63 days for a quarter
        ('investment_period', 63),  # 63 days for a quarter
    )

    def __init__(self):
        self.investment_vehicles = self.datas
        self.ranking = []
        self.timer = 0

    def next(self):
        if self.timer % self.params.investment_period == 0:
            self.rank_investment_vehicles()
            self.rebalance_portfolio()
        self.timer += 1

    def rank_investment_vehicles(self):
        self.ranking = sorted(
            self.investment_vehicles,
            key=lambda vehicle: vehicle.close[-self.params.ranking_period] / vehicle.close[0] - 1,
            reverse=True
        )

    def rebalance_portfolio(self):
        self.order_target_percent(self.ranking[0], target=1.0)
        for vehicle in self.ranking[1:]:
            self.order_target_percent(vehicle, target=0.0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    vfinx = bt.feeds.YahooFinanceData(
        dataname='VFINX',
        fromdate=datetime.datetime(1991, 1, 1),
        todate=datetime.datetime(2011, 12, 31),
    )
    vustx = bt.feeds.YahooFinanceData(
        dataname='VUSTX',
        fromdate=datetime.datetime(1991, 1, 1),
        todate=datetime.datetime(2011, 12, 31),
    )
    cerebro.adddata(vfinx)
    cerebro.adddata(vustx)
    cerebro.addstrategy(MomentumRanking)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
    print(f"Final Portfolio Value: {cerebro.broker.getvalue()}")
```