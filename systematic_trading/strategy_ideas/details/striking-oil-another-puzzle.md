<div align="center">
  <h1>Striking Oil: Another Puzzle?</h1>
</div>

## Original paper

📕 [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=460500)

## Trading rules

- Use various oil types (Brent, WTI, Dubai, etc.) with minimal differences in outcomes; Arab Light crude oil is utilized in the source paper
- Employ monthly oil returns as the independent variable and equity returns as the dependent variable in a regression equation
- Re-estimate the model monthly, incorporating last month’s observations
- Compare the predicted stock market return for a specific month (based on regression results and conditional on previous month’s oil price change) to the risk-free rate
- Invest fully in the market portfolio if expected return is higher (bull market); otherwise, invest in cash (bear market)

## Statistics

- **Markets Traded:** Equities
- **Period of Rebalancing:** Monthly
- **Backtest period:** 1988-2003
- **Annual Return:** 11.9%
- **Maximum Drawdown:** N/A
- **Sharpe Ratio:** 0.81
- **Annual Standard Deviation:** 9.8%

## Python code

### Backtrader

```python
import backtrader as bt
import numpy as np
from scipy import stats

class OilEquityStrategy(bt.Strategy):
    params = (
        ('oil_data', None),
        ('risk_free_rate', 0.0),
    )

    def __init__(self):
        self.oil_returns = self.p.oil_data
        self.equity_returns = self.data.close
        self.current_month = None
        self.invest_in_market = False

    def next(self):
        current_date = self.datetime.date(0)

        if current_date.month != self.current_month:
            self.current_month = current_date.month

            # Calculate returns
            oil_monthly_returns = self.oil_returns[-1]
            equity_monthly_returns = self.equity_returns[-1]

            # Regression
            slope, intercept, _, _, _ = stats.linregress(oil_monthly_returns, equity_monthly_returns)

            # Estimate return
            predicted_return = intercept + slope * oil_monthly_returns[-1]

            # Compare predicted return with risk-free rate
            if predicted_return > self.p.risk_free_rate:
                self.invest_in_market = True
            else:
                self.invest_in_market = False

        if self.invest_in_market:
            self.order_target_percent(target=1)
        else:
            self.order_target_percent(target=0)

# Create and run Backtrader strategy
cerebro = bt.Cerebro()
cerebro.addstrategy(OilEquityStrategy, oil_data=<YOUR_OIL_DATA>, risk_free_rate=<YOUR_RISK_FREE_RATE>)
cerebro.adddata(<YOUR_EQUITY_DATA>)
results = cerebro.run()
```

Replace `<YOUR_OIL_DATA>`, `<YOUR_RISK_FREE_RATE>`, and `<YOUR_EQUITY_DATA>` with the appropriate data for your backtest.