<div align="center">
  <h1>US Dollar Carry Trades in the Era of ‘Cheap Money’</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2765552)

## Trading rules

- Investment universe: developed country currencies (Euro area, Australia, Canada, Denmark, Japan, New Zealand, Norway, Sweden, Switzerland, UK)
- Calculate Average Forward Discount (AFD) with equal weights or use average 3-month rate
- Compare AFD to 3-month US Treasury rate
- Long US dollar, short currency basket if 3-month US Treasury rate > AFD
- Short US dollar, long currency basket if 3-month US Treasury rate < AFD
- Rebalance portfolio monthly

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1983-2009
- **Annual Return:** 5.6%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.66
- **Annual Standard Deviation:** 8.53%

## Python code

### Backtrader

```python
import backtrader as bt

class DollarCarryTradeStrategy(bt.Strategy):
    params = (
        ("rebalance_days", 30),
    )

    def __init__(self):
        self.currency_list = ["EURUSD", "AUDUSD", "CADUSD", "DKKUSD", "JPYUSD", "NZDUSD", "NOKUSD", "SEKUSD", "CHFUSD", "GBPUSD"]
        self.data_dict = {currency: self.getdatabyname(currency) for currency in self.currency_list}
        self.rebalance_timer = 0

    def next(self):
        if self.rebalance_timer % self.params.rebalance_days == 0:
            self.rebalance_portfolio()
        self.rebalance_timer += 1

    def rebalance_portfolio(self):
        afd = sum([self.data_dict[currency].close[0] for currency in self.currency_list]) / len(self.currency_list)
        us_treasury_rate = self.data_dict["USD_3M_TREASURY_RATE"].close[0]

        if us_treasury_rate > afd:
            for currency in self.currency_list:
                self.sell(data=self.data_dict[currency], size=1)
        else:
            for currency in self.currency_list:
                self.buy(data=self.data_dict[currency], size=1)

cerebro = bt.Cerebro()

# Add currency pair data feeds
for currency in ["EURUSD", "AUDUSD", "CADUSD", "DKKUSD", "JPYUSD", "NZDUSD", "NOKUSD", "SEKUSD", "CHFUSD", "GBPUSD"]:
    data = bt.feeds.GenericCSVData(
        dataname=f"{currency}.csv",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat="%Y-%m-%d",
        timeframe=bt.TimeFrame.Days,
        compression=1,
    )
    cerebro.adddata(data, name=currency)

# Add US Treasury rate data feed
treasury_rate_data = bt.feeds.GenericCSVData(
    dataname="USD_3M_TREASURY_RATE.csv",
    datetime=0,
    close=1,
    dtformat="%Y-%m-%d",
    timeframe=bt.TimeFrame.Days,
    compression=1,
)
cerebro.adddata(treasury_rate_data, name="USD_3M_TREASURY_RATE")

cerebro.addstrategy(DollarCarryTradeStrategy)
cerebro.run()
```

Keep in mind that you’ll need to provide the appropriate data for each currency in CSV format, as well as for the 3-month US Treasury rate. The code assumes that these CSV files are named as the corresponding currency symbol with a “.csv” extension (e.g., “EURUSD.csv”).