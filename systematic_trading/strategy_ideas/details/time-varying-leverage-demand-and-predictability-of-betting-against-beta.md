<div align="center">
  <h1>Time-Varying Leverage Demand and Predictability of Betting-Against-Beta</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3194626)

## Trading rules

- Investment universe: All country ETFs
- Calculate beta: 1-year rolling window, relative to MSCI US Equity Index
- Rank ETFs: Ascending order by beta
- Assign portfolios: Low-beta and high-beta groups
- Weight securities: Based on ranked betas
- Rebalance monthly: Adjust portfolios each calendar month
- Rescale portfolios: Set both low-beta and high-beta betas to one at formation
- Betting-Against-Beta strategy: Long on low-beta, short on high-beta (zero-cost, zero-beta)
- Potential modifications: Long/short positions in extreme beta deciles for improved performance

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1980-2009
- **Annual Return:** 9.77%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.31
- **Annual Standard Deviation:** 18.46%

## Python code

### Backtrader

```python
import backtrader as bt
import pandas as pd
import numpy as np

class BettingAgainstBeta(bt.Strategy):
    params = (
        ('beta_window', 252),  # 1-year rolling window for beta calculation
        ('rebalance_freq', 20)  # Monthly rebalancing
    )

    def __init__(self):
        self.etfs = self.datas[1:]  # All country ETFs
        self.msci_index = self.datas[0]  # MSCI US Equity Index
        self.counter = 0

    def next(self):
        self.counter += 1
        if self.counter % self.params.rebalance_freq == 0:
            etf_betas = []
            for etf in self.etfs:
                returns_etf = pd.Series(etf.get_array('close')[-self.params.beta_window:]).pct_change().dropna()
                returns_index = pd.Series(self.msci_index.get_array('close')[-self.params.beta_window:]).pct_change().dropna()
                beta = np.cov(returns_etf, returns_index)[0][1] / np.var(returns_index)
                etf_betas.append((etf, beta))
            etf_betas.sort(key=lambda x: x[1])  # Sort ETFs in ascending order by beta
            low_beta_etfs = etf_betas[:len(etf_betas) // 2]
            high_beta_etfs = etf_betas[len(etf_betas) // 2:]

            # Adjust positions - long on low-beta, short on high-beta
            for etf, beta in low_beta_etfs:
                self.order_target_percent(etf, target=1 / len(low_beta_etfs))
            for etf, beta in high_beta_etfs:
                self.order_target_percent(etf, target=-1 / len(high_beta_etfs))

if __name__ == '__main__':
    cerebro = bt.Cerebro()

    # Load data for MSCI US Equity Index and Country ETFs
    # Assuming historical data is available as csv files
    msci_index_data = bt.feeds.YahooFinanceCSVData(dataname='path_to_msci_index_csv')
    etf_list = ['path_to_etf1_csv', 'path_to_etf2_csv', 'path_to_etf3_csv', ...]

    cerebro.adddata(msci_index_data)
    for etf_data_path in etf_list:
        etf_data = bt.feeds.YahooFinanceCSVData(dataname=etf_data_path)
        cerebro.adddata(etf_data)

    cerebro.addstrategy(BettingAgainstBeta)
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.001)  # Set broker commission

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
```

Note: Make sure to replace the ‘path_to_msci_index_csv’, ‘path_to_etf1_csv’, ‘path_to_etf2_csv’, ‘path_to_etf3_csv’, … with the actual file paths for the MSCI US Equity Index and country ETFs historical data.