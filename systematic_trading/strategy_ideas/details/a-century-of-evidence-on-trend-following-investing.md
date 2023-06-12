<div align="center">
  <h1>A Century of Evidence on Trend-Following Investing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)

## Trading rules

- Investment universe consists of 24 commodity futures, 12 cross-currency pairs (with nine underlying currencies), nine developed equity indices, and 13 developed government bond futures.
- Consider the excess return of each asset over the past 12 months.
- Go long on the contract if the excess return is positive.
- Go short on the contract if the excess return is negative.
- The position size is inversely proportional to the instrument’s volatility.
- A univariate GARCH model is used to estimate ex-ante volatility.
- Other simple models could easily be used (e.g., historical volatility).
- Portfolio is rebalanced monthly.

## Statistics

- **Markets Traded:** Bonds, commodities, currencies, equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1965-2009
- **Annual Return:** 16.21%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 1.04
- **Annual Standard Deviation:** 11.73%

## Python code

### Backtrader

```python
# Import necessary libraries
import backtrader as bt
import pandas as pd
import numpy as np

class MultiAssetVolatilityStrategy(bt.Strategy):

    # Define the list of assets in our investment universe
    assets = ['COMMODITY_FUTURES', 'CROSS_CURRENCY_PAIRS', 'EQUITY_INDICES', 'GOVERNMENT_BOND_FUTURES']

    # Define the parameters for our strategy
    period = 12 # Number of months to consider for excess return calculation
    garch_p = 1 # GARCH(p,q) model parameter (p)
    garch_q = 1 # GARCH(p,q) model parameter (q)

    # Define the start and end dates for our backtest
    start_date = '2000-01-01'
    end_date = '2019-12-31'

    def __init__(self):

        # Define a dictionary to store the assets' data
        self.data_dict = {}

        # Loop through each asset and add its data to the dictionary
        for asset in self.assets:

            # Load the data for the asset
            price_data = pd.read_csv(f'{asset}.csv', index_col='Date', parse_dates=True)

            # Calculate the excess return for the asset
            excess_return = price_data.pct_change(self.period).iloc[-1] - 0.03 / 252

            # Create a data feed for the asset
            self.data_dict[asset] = bt.feeds.PandasData(dataname=excess_return, name=asset, fromdate=self.start_date, todate=self.end_date)

            # Define a GARCH model for the asset's volatility
            self.data_dict[asset].volatility = bt.indicators.Garch(p=self.garch_p, q=self.garch_q)

            # Set the position size as inversely proportional to the asset's volatility
            self.data_dict[asset].volatility_label = f'{asset}_volatility'
            self.data_dict[asset].volatility_adjusted = self.params.size / self.data_dict[asset].volatility
            self.data_dict[asset].volatility_adjusted_label = f'{asset}_volatility_adjusted'

            # Define a position for each asset
            self.order_dict = {}

            # Loop through each asset and create a position for it
            for asset, data in self.data_dict.items():
                self.order_dict[asset] = self.buy(size=data.volatility_adjusted, exectype=bt.Order.Market, stake=100)

    def next(self):

        # Rebalance the portfolio on a monthly basis
        if self.datetime.month != self.datetime(-1).month:

            # Sell any assets that are no longer in our investment universe
            for asset in self.order_dict.keys():
                if asset not in self.assets:
                    self.close(self.order_dict[asset])

            # Loop through each asset and update its position based on the latest excess return and volatility
            for asset, data in self.data_dict.items():
                if asset in self.assets:
                    if data[0] > 0:
                        self.order_dict[asset].size = data.volatility_adjusted
                        self.sell(self.order_dict[asset], size=data.volatility_adjusted, exectype=bt.Order.Market, stake=100)
                    else:
                        self.order_dict[asset].size = -data.volatility_adjusted
                        self.buy(self.order_dict[asset], size=data.volatility_adjusted, exectype=bt.Order.Market, stake=100)
```