<div align="center">
  <h1>How Do Factor Premia Vary Over Time? A Century of Evidence</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3400998)

## Trading rules

- Create an investment universe containing investable asset classes
- Find a good tracking vehicle for each asset class
- Momentum ranking is done on price series
- Valuation ranking is done on adjusted yield measure for each asset class
- E/P (Earning/Price) measure is used for stocks, and YTM (Yield-to-maturity) is used for bonds
- Adjusted structural yields for each asset class by specific percentages
- Rank each asset class by 12-month momentum, 1-month momentum, and by valuation
- Weight all three strategies (25% weight to 12m momentum, 25% weight to 1-month momentum, 50% weight to value strategy)
- Go long top quartile portfolio
- Go short bottom quartile portfolio.

## Statistics

- **Markets Traded:** Bonds, equities, REITs
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1986-2007
- **Annual Return:** 11.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.79
- **Annual Standard Deviation:** 10%

## Python code

### Backtrader

```python
# Create an investment universe containing investable asset classes
universe = ['Stocks', 'Bonds', 'Commodities', 'Real Estate']

# Find a good tracking vehicle for each asset class
tracking_vehicle = {'Stocks': 'SPY', 'Bonds': 'AGG', 'Commodities': 'DBC', 'Real Estate': 'VNQ'}

# Momentum ranking is done on price series
def momentum_ranking(data):
     return data / data.shift(12) - 1, data / data.shift(1) - 1

# Valuation ranking is done on adjusted yield measure for each asset class
def valuation_ranking(data, asset_class):
     if asset_class == 'Stocks':
         return data.earning / data.price
     elif asset_class == 'Bonds':
         return data.yield_to_maturity
     elif asset_class == 'Commodities':
         return data.adjusted_yield * 1.1
     elif asset_class == 'Real Estate':
         return data.adjusted_yield * 0.9

# Adjusted structural yields for each asset class by specific percentages
def adjust_yield(data, asset_class):
     if asset_class == 'Stocks':
         return data
     elif asset_class == 'Bonds':
         return data.adjusted_yield * 1.05
     elif asset_class == 'Commodities':
         return data.adjusted_yield * 1.1
     elif asset_class == 'Real Estate':
         return data.adjusted_yield * 0.9

# Rank each asset class by 12-month momentum, 1-month momentum, and by valuation
def rank_assets(data):
    rank = (momentum_ranking(data.price)[0].rank(axis=1, ascending=False) * 0.25
            + momentum_ranking(data.price)[1].rank(axis=1, ascending=False) * 0.25
            + valuation_ranking(data, asset_class).rank(axis=1, ascending=False) * 0.5)
    return rank

# Weight all three strategies (25% weight to 12m momentum, 25% weight to 1-month momentum, 50% weight to value strategy)
asset_weight = {'12m_momentum': 0.25, '1m_momentum': 0.25, 'value': 0.5}

# Go long top quartile portfolio
def go_long(data):
     rank = rank_assets(data)
     top = rank.iloc[:, :int(len(rank.columns) / 4)]
     top_weights = top.apply(lambda x: x / x.sum())
     return top_weights

# Go short bottom quartile portfolio.
def go_short(data):
     rank = rank_assets(data)
     bottom = rank.iloc[:, -int(len(rank.columns) / 4):]
     bottom_weights = bottom.apply(lambda x: -1 * x / abs(x.sum()))
     return bottom_weights
```