<div align="center">
  <h1>Risk Adjusted Momentum Strategies: A Comparison between Constant and Dynamic Volatility Scaling Approaches</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3076715)

## Trading rules

- Investment universe: 18 futures contracts (7 currency, 6 stock index, 5 fixed income)
    - Currency futures: Euro/USD, Yen/USD, CAD/USD, GBP/USD, AUD/USD, CHF/USD, USD index
    - Stock index futures: CAC 40, FTSE 100, Nikkei 225, S&P 500, Swiss Market Index, Dow Jones EURO STOXX 50
    - Fixed income futures: Euro Bund 10-year, Canadian Govt Bond 10-year, U.S. Treasury Note 2-year, U.S. Treasury Note 5-year, U.S. Treasury Note 10-year
- Rank futures contracts every 6 months based on 6-month performance
- Long top 6 performers; short bottom 6 performers
- Equally weighted portfolio
- Rebalance every 6 months

## Statistics

- **Markets Traded:** Bonds, currencies, equities
- **Period of Rebalancing:** 6 Months
- **Backtest period:** 1991-2007
- **Annual Return:** 6.49%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.5
- **Annual Standard Deviation:** 12.91%

## Python code

### Backtrader

```python
import backtrader as bt

class MomentumFutures(bt.Strategy):
    params = (
        ('momentum_period', 126),  # 6 months momentum period
        ('rebalance_days', 126),   # Rebalance every 6 months
    )

    def __init__(self):
        self.future_names = [
            # Currency futures
            'EURUSD', 'JPYUSD', 'CADUSD', 'GBPUSD', 'AUDUSD', 'CHFUSD', 'USDIDX',
            # Stock index futures
            'CAC40', 'FTSE100', 'NIKKEI225', 'SP500', 'SMI', 'DJEUROSTOXX50',
            # Fixed income futures
            'EUROBUND10Y', 'CGB10Y', 'USTNOTE2Y', 'USTNOTE5Y', 'USTNOTE10Y',
        ]
        self.momentum = {data: bt.indicators.Momentum(data, period=self.params.momentum_period) for data in self.datas}
        self.rebalance_countdown = self.params.rebalance_days

    def next(self):
        if self.rebalance_countdown > 0:
            self.rebalance_countdown -= 1
        else:
            self.rebalance_countdown = self.params.rebalance_days

            # Rank futures based on 6-month performance
            rankings = list(self.datas)
            rankings.sort(key=lambda data: self.momentum[data][0], reverse=True)

            # Long top 6 and short bottom 6 performers
            for i, data in enumerate(rankings):
                position_size = 1 / 12
                if i < 6:
                    self.order_target_percent(data, target=position_size)
                elif i >= len(rankings) - 6:
                    self.order_target_percent(data, target=-position_size)
                else:
                    self.order_target_percent(data, target=0)

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MomentumFutures)

    # Add futures data feeds
    for future_name in MomentumFutures.future_names:
        data = bt.feeds.YourDataFeed(dataname=future_name)  # Replace 'YourDataFeed' with the actual data feed class
        cerebro.adddata(data)

    cerebro.run()
```

Please replace ‘YourDataFeed’ with the actual data feed class that you are using for your backtesting.