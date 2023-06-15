<div align="center">
  <h1>Option Returns and Volatility Mispricing</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=889947)

## Trading rules

Here are the trading rules of the given investment strategy:

- The investment universe is limited to all US based stocks with liquid options.
- Every month, the investor computes the slope of the volatility term structure for each stock.
- The slope of the volatility term structure is defined as the difference between the long-term and short-term volatility.
- The short-term volatility is defined as the average of the one-month ATM put and call implied volatilities.
- The long-term volatility is the average volatility of the ATM put and call options, with the longest time-to-maturity available and the same strike as that of the short-term options.
- The longest time to expiration is between 50 and 360 days.
- Every month, the investor forms ten portfolios based on the slope of the volatility term structure.
- Decile portfolios contain delta hedged one-month call ATM options available on the second trading day after the expiration of the previous options.
- The strike price is set as close as possible to the closing price.
- The investor goes long on the delta hedged decile with the highest slope in the volatility term structure.
- The investor goes short on the decile with the lowest slope in the volatility term structure.
- The portfolio is equally weighted and rebalanced monthly.

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1996-2007
- **Annual Return:** 19.56%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.74
- **Annual Standard Deviation:** 21.13%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class InvestmentUniverse():
    def __init__(self, symbol):
        self.symbol = symbol

    def filter_universe(self, start, end):
        # Filter universe of US-based stocks with liquid options
        self.df = pd.read_csv(f"{self.symbol}.csv", parse_dates=['date'], index_col='date')
        self.df = self.df[(self.df.index >= start) & (self.df.index <= end)]
        self.df = self.df[self.df['volume'] > 500000]

class SlopeVolatility():
    def __init__(self):
        self.df = pd.DataFrame(columns=['short_vol', 'long_vol', 'slope'])

    def get_short_vol(self, df):
        # Short-term volatility is the average of the one-month ATM put and call implied volatilities
        short_vol = (df['put_volatility'] + df['call_volatility']) / 2
        return short_vol.mean()

    def get_long_vol(self, df):
        # Long-term volatility is the average volatility of the ATM put and call options,
        # with the longest time-to-maturity available and the same strike as that of the short-term options
        # The longest time to expiration is between 50 and 360 days
        long_df = df[(df['days_to_expire'] >= 50) & (df['days_to_expire'] <= 360)]
        if long_df.empty:
            long_vol = np.nan
        else:
            long_vol = long_df.loc[long_df['strike'] == df['strike'].iloc[0], 'mid_volatility'].mean()
        return long_vol

    def compute_slope(self, short_vol, long_vol):
        # Slope of the volatility term structure is defined as the difference between the long-term and short-term volatility
        slope = long_vol - short_vol
        return slope

    def get_slope(self, df):
        short_vol = self.get_short_vol(df)
        long_vol = self.get_long_vol(df)
        slope = self.compute_slope(short_vol, long_vol)
        return slope

    def compute_slope_volatility(self, df):
        self.df = df.groupby('symbol').apply(self.get_slope).reset_index().rename(columns={0: 'slope'})

class DecilePortfolio():
    def __init__(self):
        self.df = pd.DataFrame()

    def get_strike(self, df):
        # The strike price is set as close as possible to the closing price
        idx = (np.abs(df['prev_close'] - df['strike'])).argmin()
        strike = df.loc[idx, 'strike']
        return strike

    def get_options(self, df):
        # Delta-hedged one-month call ATM options available on the second trading day after the expiration of the previous options
        # The strike price is set as close as possible to the closing price
        expiry = df.index[0].replace(day=1) + pd.DateOffset(months=1) + pd.DateOffset(days=1)
        expiry = expiry.date()
        strike = self.get_strike(df)
        call_option = f"{df.iloc[0]['symbol']} {expiry} C {strike}"
        put_option = f"{df.iloc[0]['symbol']} {expiry} P {strike}"
        return call_option, put_option

    def form_decile_portfolios(self, slope_vol_df):
        # Every month, form ten portfolios based on the slope of the volatility term structure
        deciles = slope_vol_df['slope'].quantile(np.arange(0.1, 1, 0.1)).reset_index()
        deciles = deciles.rename(columns={'index': 'decile', 'slope': 'slope_cutoff'})
        self.df = pd.DataFrame()
        for i in range(1, 11):
            decile = deciles[(deciles['decile'] == i) | (deciles['decile'] == i-1)]
            decile_df = pd.merge(slope_vol_df, decile, on='slope', how='inner')
            decile_df['long_short'] = np.where(decile_df['slope'] >= decile.iloc[0]['slope_cutoff'], 'long', 'short')
            decile_df = decile_df.sort_values(by='slope', ascending=False).reset_index(drop=True)
            decile_df['call_option'], decile_df['put_option'] = zip(*decile_df.groupby('symbol').apply(self.get_options))
            self.df = self.df.append(decile_df)
        self.df = self.df[['symbol', 'long_short', 'call_option', 'put_option']].reset_index(drop=True)

class Investor():
    def __init__(self):
        self.portfolio_value = 1000000

    def run_investment_strategy(self, start, end):
        universe = InvestmentUniverse('us_stock')
        universe.filter_universe(start, end)
        slope_volatility = SlopeVolatility()
        slope_volatility.compute_slope_volatility(universe.df)
        decile_portfolio = DecilePortfolio()
        decile_portfolio.form_decile_portfolios(slope_volatility.df)
        self.execute_trades(decile_portfolio.df)

    def execute_trades(self, decile_portfolio_df):
        current_month = None
        for index, row in decile_portfolio_df.iterrows():
            date = row['date']
            month = date.month
            if current_month is not None and month != current_month:
                self.rebalance_portfolio()
            if row['long_short'] == 'long':
                self.go_long(row['call_option'], row['put_option'])
            else:
                self.go_short(row['call_option'], row['put_option'])
            current_month = month

    def go_long(self, call_option, put_option):
        # Buy delta-hedged call option and sell delta-hedged put option to go long
        pass

    def go_short(self, call_option, put_option):
        # Sell delta-hedged call option and buy delta-hedged put option to go short
        pass

    def rebalance_portfolio(self):
        # Rebalance portfolio to equally weighted
        pass

investor = Investor()
investor.run_investment_strategy('2021-01-01', '2021-12-31')
```