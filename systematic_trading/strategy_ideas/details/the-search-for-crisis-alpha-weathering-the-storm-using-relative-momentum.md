<div align="center">
  <h1>The Search for Crisis Alpha: Weathering the Storm Using Relative Momentum</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2739520)

## Trading rules

- Use 5 U.S. Treasuries ETFs with different maturities
- Look at absolute momentum of each asset by centering momentum search around 9 months and neglecting previous month’s return
- Utilize return of 1-year Treasuries to calculate excess return of each asset
- Include any asset exhibiting positive momentum in portfolio
- If no assets are exhibiting positive momentum, give full weight to 1-year U.S. Treasuries
- Focus on relative momentum by using ranks of assets instead of specific values of risk-adjusted return
- Rankweight assets based on weights proportional to excess return divided by variance
- Rebalance portfolio on monthly basis

## Statistics

- **Markets Traded:** U.S. Treasuries
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1962-2014
- **Annual Return:** 7%
- **Maximum Drawdown:** -6%
- **Sharpe Ratio:** 1
- **Annual Standard Deviation:** 5%

## Python code

### Backtrader

```python
import backtrader as bt

# Create list of 5 US Treasuries ETF tickers
tickers = ["TLT", "IEF", "SHY", "GOVT", "VGSH"]

class AbsoluteMomentum(bt.Indicator):
    # Define indicator that calculates absolute momentum
    # Center momentum around 9 months and neglect previous month
    params = (('center', 9),)
    
    def __init__(self):
        momentum = self.data - self.data(-self.params.center)
        self.lines.mom = momentum
    
    def next(self):
        pass

class ExcessReturn(bt.Indicator):
    # Define indicator that calculates excess return of an asset
    # relative to 1-year Treasuries
    
    def __init__(self):
        excess_return = self.data - self.datas[0].close
        self.lines.excess_return = excess_return
    
    def next(self):
        pass

class MomentumRank(bt.Strategy):
    # Define strategy that focuses on relative momentum using ranks
    
    def __init__(self):
        self.inds = {}
        # Create list of data feeds for each ETF ticker
        self.assets = [self.getdatabyname(ticker) for ticker in tickers]
        # Calculate absolute momentum and excess return for each asset
        for asset in self.assets:
            self.inds[asset] = {}
            self.inds[asset]['abs_mom'] = AbsoluteMomentum(asset.close)
            self.inds[asset]['excess_return'] = ExcessReturn(asset.close)

    def next(self):
        signals = []
        # Check for positive momentum in each asset
        for asset in self.assets:
            mom = self.inds[asset]['abs_mom']
            excess_return = self.inds[asset]['excess_return']
            # If absolute momentum is positive, add to signals list
            if mom > 0:
                rankweight = excess_return / (bt.var(excess_return) or 1)
                signals.append((asset, rankweight))
        
        # If no assets have positive momentum, give full weight to 1-year Treasuries
        if not signals:
            signals.append((self.datas[0], 1))
        
        # Rankweight assets based on weights proportional to excess return divided by variance
        signals.sort(key=lambda x: x[1], reverse=True)
        weights = {}
        total_weight = 0
        for i, (asset, rankweight) in enumerate(signals):
            weight = rankweight / sum([x[1] for x in signals])
            weights[asset] = weight
            total_weight += weight
            self.log('{} - Rankweight: {:.2f}%, Weight: {:.2f}%'.format(asset._name, rankweight * 100, weight * 100))
        
        # Rebalance portfolio on monthly basis
        if self.datas[0].datetime.date().day == 1:
            for asset, weight in weights.items():
                self.order_target_percent(asset, target=weight / total_weight)
```