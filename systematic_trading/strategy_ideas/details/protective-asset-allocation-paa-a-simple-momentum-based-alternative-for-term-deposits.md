<div align="center">
  <h1>Protective Asset Allocation (PAA): A Simple Momentum-Based Alternative for Term Deposits</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734)

## Trading rules

- Investment universe: 12 ETFs across various asset classes
    - US equity: SPY, QQQ, IWM
    - Advanced countries’ equity: VGK, EWJ
    - Emerging market equity: EEM
    - Alternative assets: GSG (commodities), GLD (gold), IYR (REITs)
    - Risky bonds: HYG, LQD, TLT
    - Safe bonds: IEF (intermediate US treasuries)
- Trading rules:
    - Determine good and bad assets using 12-month momentum indicator (MOM>0)
    - Calculate bond fraction with protection factor a=2
    - Select top 6 good assets (or fewer if less than 6 have MOM>0)
    - Calculate share of risky assets as (1-BF)/BF
    - Equally weight assets in the risky portfolio

## Statistics

- **Markets Traded:** Bonds, commodities, equities, REITs
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1993-2015
- **Annual Return:** 10.5%
- **Maximum Drawdown:** -8.8%
- **Sharpe Ratio:** 0.82
- **Annual Standard Deviation:** 7.9%

## Python code

### Backtrader

```python
import backtrader as bt

class MultiAssetMomentum(bt.Strategy):
    params = (
        ('lookback_period', 12),
        ('protection_factor', 2),
        ('num_assets', 6)
    )

    def __init__(self):
        self.assets = self.datas[1:]
        self.safe_bond = self.datas[0]
        self.momentum = {asset: bt.indicators.Momentum(asset.close, period=self.p.lookback_period) for asset in self.assets}

    def next(self):
        good_assets = [asset for asset in self.assets if self.momentum[asset][0] > 0]
        good_assets.sort(key=lambda asset: self.momentum[asset][0], reverse=True)
        selected_assets = good_assets[:self.p.num_assets]
        bond_fraction = 1 / (1 + self.p.protection_factor * len(selected_assets))

        for asset in self.assets:
            if asset in selected_assets:
                target_weight = (1 - bond_fraction) / len(selected_assets)
            elif asset == self.safe_bond:
                target_weight = bond_fraction
            else:
                target_weight = 0

            self.order_target_percent(asset, target_weight)

# Instantiate Cerebro
cerebro = bt.Cerebro()

# Add data feeds
etf_symbols = ['IEF', 'SPY', 'QQQ', 'IWM', 'VGK', 'EWJ', 'EEM', 'GSG', 'GLD', 'IYR', 'HYG', 'LQD', 'TLT']
for symbol in etf_symbols:
    data = bt.feeds.YahooFinanceData(dataname=symbol, fromdate='2000-01-01', todate='2021-09-01', reverse=False)
    cerebro.adddata(data)

# Add strategy
cerebro.addstrategy(MultiAssetMomentum)

# Run backtest
result = cerebro.run()
```