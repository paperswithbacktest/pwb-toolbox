<div align="center">
  <h1>ANANTA: A Systematic Quantitative FX Trading Strategy</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2419243)

## Trading rules

- Investment universe: 11 main currencies (AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, NZD, SEK, USD) and their cross-pairs
- Interest rate differential momentum: +1/-1 signal based on IR differential compared to 15-day simple moving average
- Sub-signal calculation: For each currency cross-pair
- Net position: Sum of signals for each currency (refer to page 12 for detailed explanation)
- Portfolio rebalancing: Twice daily - London close and New York close times

## Statistics

- **Markets Traded:** Currencies
- **Period of Rebalancing:** Intraday
- **Backtest period:** 2003-2014
- **Annual Return:** 8.81%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.65
- **Annual Standard Deviation:** 5.33%

## Python code

### Backtrader

```python
import backtrader as bt
import backtrader.feeds as btfeeds

class InterestRateMomentum(bt.Strategy):
    params = (
        ('period', 15),
    )

    def __init__(self):
        self.currencies = ['AUD', 'CAD', 'CHF', 'DKK', 'EUR', 'GBP', 'JPY', 'NOK', 'NZD', 'SEK', 'USD']
        self.currency_pairs = [c1 + c2 for c1 in self.currencies for c2 in self.currencies if c1 != c2]
        self.ird_momentum = {pair: bt.indicators.SimpleMovingAverage(self.getdatabyname(pair).interest_rate_diff, period=self.params.period) for pair in self.currency_pairs}

    def next(self):
        signals = {currency: 0 for currency in self.currencies}

        for pair in self.currency_pairs:
            data = self.getdatabyname(pair)
            ird = data.interest_rate_diff[0]
            ird_ma = self.ird_momentum[pair][0]
            signal = 1 if ird > ird_ma else -1
            base_currency, quote_currency = pair[:3], pair[3:]
            signals[base_currency] += signal
            signals[quote_currency] -= signal

        for currency, signal in signals.items():
            if signal > 0:
                self.buy(data=self.getdatabyname(currency + 'USD'))
            elif signal < 0:
                self.sell(data=self.getdatabyname(currency + 'USD'))

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    for pair in InterestRateMomentum.currency_pairs:
        data = btfeeds.GenericCSVData(
            dataname=pair + '.csv',
            dtformat=('%Y-%m-%d %H:%M:%S'),
            timeframe=bt.TimeFrame.Minutes,
            compression=1,
            sessionstart=bt.Time(num=15, unit=bt.Time.Minute),
            sessionend=bt.Time(num=21, unit=bt.Time.Minute),
            plot=False
        )
        cerebro.adddata(data, name=pair)

    cerebro.addstrategy(InterestRateMomentum)
    cerebro.run()
    cerebro.plot()
```