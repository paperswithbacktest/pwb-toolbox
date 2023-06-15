<div align="center">
  <h1>Trading volume and liquidity provision in cryptocurrency markets</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3239670)

## Trading rules

Here are the trading rules of this strategy:

- Investment universe consists of currency pairs of 26 cryptocurrencies.
- Cryptocurrency pairs are allocated into 3 groups based on their return between times t-1 and t from low to high.
- Cryptocurrency pairs are further allocated into 3 sub-groups based on the volume shock at time t from low to high.
- Volume shock is calculated for cryptocurrency pair i at time t as the log deviation from its trend estimated over a rolling period of days.
- This produces a 3x3 sort.
- A long position is taken in the low prior return and volume portfolio.
- A short position is taken in the high prior return, low volume portfolio.
- Short position could be taken using the various CFDs, however the long only strategy is also profitable.
- The strategy is rebalanced daily.

## Statistics

- **Markets Traded:** Cryptocurrencies
- **Period of Rebalancing:** Daily
- **Backtest period:** 2017-2018
- **Annual Return:** 34.26%
- **Maximum Drawdown:** Unknown
- **Sharpe Ratio:** 2.62
- **Annual Standard Deviation:** 11.56%

## Python code

### Backtrader

```python
# Import necessary libraries
import backtrader as bt
import pandas as pd
import numpy as np

class CryptocurrencyPairsStrategy(bt.Strategy):

    params = dict(
        map_file=None,
        short_period=30,
        long_period=90,
        percent_rank=0.3,
        num_groups=3,
        num_subgroups=3,
        log_shock=True,
        shock_window=20
    )

    def __init__(self):

        # Load the map file
        self.map = pd.read_csv(self.p.map_file)

        # Convert map to dict for easy access
        self.map_dict = dict(zip(self.map['PAIR'], self.map['SYMBOL']))

        # Create empty containers for each group
        self.groups = {}
        for i in range(1, self.p.num_groups + 1):
            self.groups[i] = []

        # Create empty containers for each subgroup in each group
        self.subgroups = {}
        for i in range(1, self.p.num_groups + 1):
            self.subgroups[i] = {}
            for j in range(1, self.p.num_subgroups + 1):
                self.subgroups[i][j] = []

        # Determine cryptocurrency pairs to include in each group and subgroup
        returns = self.returns(1)
        volumes = self.volumes()
        for pair in returns:
            # Calculate the prior return and volume
            prior_return = self.prior_return(pair)
            prior_volume = self.prior_volume(pair, volumes)
            # Add pair to appropriate group and subgroup
            group = self.group(prior_return)
            subgroup = self.subgroup(prior_volume, volumes[pair])
            self.groups[group].append(pair)
            self.subgroups[group][subgroup].append(pair)

    def returns(self, days):
        """Calculate returns for all pairs over past `days`"""
        returns = {}
        for pair in self.map['PAIR']:
            symbol = self.map_dict[pair]
            data = self.getdatabyname(symbol)
            if data:
                # Calculate return between t-`days` and t for each pair
                close_tminusdays = data.close[-days-1]
                close_t = data.close[-1]
                returns[pair] = (close_t - close_tminusdays) / close_tminusdays
        return returns

    def volumes(self):
        """Calculate volumes for all pairs"""
        volumes = {}
        for pair in self.map['PAIR']:
            symbol = self.map_dict[pair]
            data = self.getdatabyname(symbol)
            if data:
                # Calculate volume at time t for each pair
                volumes[pair] = data.volume[-1]
        return volumes

    def prior_return(self, pair):
        """Calculate prior return for a specific pair"""
        returns = self.returns(self.p.long_period)
        return returns.get(pair, 0)

    def prior_volume(self, pair, volumes):
        """Calculate prior volume for a specific pair"""
        window = self.p.short_period
        if self.p.log_shock:
            window = self.p.shock_window
        log_deviations = self.log_deviations(pair, window)
        if len(log_deviations) == 0:
            return 0
        return log_deviations[-1]

    def log_deviations(self, pair, window):
        """Calculate log deviations from trend for a specific pair"""
        symbol = self.map_dict[pair]
        data = self.getdatabyname(symbol)
        if data:
            volumes = np.log(data.volume[-window:])
            slope, intercept = np.polyfit(range(window), volumes, 1)
            deviations = volumes - (slope * range(window) + intercept)
            return deviations[:-1]
        return []

    def group(self, prior_return):
        """Determine group based on prior return"""
        groups = np.linspace(0, 1, self.p.num_groups+1)[1:-1]
        group = 1
        for g in groups:
            if prior_return < g:
                break
            group += 1
        return group

    def subgroup(self, prior_volume, volume):
        """Determine subgroup based on prior volume and volume"""
        subgroups = np.linspace(0, 1, self.p.num_subgroups+1)[1:-1]
        subgroup = 1
        for sg in subgroups:
            if prior_volume < sg * np.log(volume):
                break
            subgroup += 1
        return subgroup

    def next(self):

        # Close existing positions
        for d in self.datas:
            if self.getposition(data=d):
                self.close(data=d)

        # Open new positions
        low_return_volume_pairs = self.subgroups[1][1]
        high_return_low_volume_pairs = self.subgroups[self.p.num_groups][1]
        for pair in low_return_volume_pairs:
            symbol = self.map_dict[pair]
            self.buy(data=self.getdatabyname(symbol))
        for pair in high_return_low_volume_pairs:
            symbol = self.map_dict[pair]
            self.sell(data=self.getdatabyname(symbol))

    def stop(self):
        """Rebalance daily"""
        self.rebalance_daily()

    def rebalance_daily(self):
        """Rebalance all positions to equal weights"""
        pos_size = 1 / (len(self.subgroups[1][1]) + len(self.subgroups[self.p.num_groups][1]))
        for d in self.datas:
            if self.getposition(data=d).size != 0:
                self.order_target_percent(data=d, target=pos_size)
```