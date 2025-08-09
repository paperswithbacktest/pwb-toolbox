<div align="center">
  <img src="static/images/systematic-trading.jpeg" height=200 alt=""/>
  <h1>Papers With Backtest Toolbox</h1>
</div>

The `pwb-toolbox` package is designed to provide tools and resources for systematic trading strategies. It includes datasets and strategy ideas to assist in developing and backtesting trading algorithms. For detailed instructions on how to use this package effectively, please refer to the associated Substack publication by visiting: https://blog.paperswithbacktest.com/.


## Installation

To install the pwb-toolbox package:

```bash
pip install pwb-toolbox
```
This package requires Python 3.10 or higher.

To login to Huggingface Hub (where PWB datasets are hosted) with Access Token

```bash
huggingface-cli login
```

## Usage

The `pwb-toolbox` package offers a range of functionalities for systematic trading analysis. Here are some examples of how to utilize the package:

### Datasets

- Import `pwb_toolbox.datasets` and sequentially loads datasets for different asset classes, such as bonds, commodities, cryptocurrencies, ETFs, forex, indices, and stocks, using the `load_dataset` function:

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.get_pricing(["AAPL", "MSFT", "GOOGL"])
df = pwb_ds.load_dataset("Bonds-Daily-Price")
df = pwb_ds.load_dataset("Commodities-Daily-Price")
df = pwb_ds.load_dataset("Cryptocurrencies-Daily-Price")
df = pwb_ds.load_dataset("ETFs-Daily-Price")
df = pwb_ds.load_dataset("Forex-Daily-Price")
df = pwb_ds.load_dataset("Indices-Daily-Price")
df = pwb_ds.load_dataset("Stocks-Daily-Price")

```

- Load daily stock price data for specific symbols using the load_dataset function. The first call retrieves data for Apple and Microsoft. The second call retrieves the same stocks but without price adjustments (`adjust=False`). The third call loads daily price data for the S&P 500 index:

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "Stocks-Daily-Price",
    ["AAPL", "MSFT"],
)

df = pwb_ds.load_dataset(
    "Stocks-Daily-Price",
    ["AAPL", "MSFT"],
    adjust=False,
)

df = pwb_ds.load_dataset(
    "Stocks-Daily-Price",
    ["sp500"],
)
```

- The `extend=True` argument instructs the function to return an extended historical data using indices, commodities, and bonds data.

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "ETFs-Daily-Price",
    ["SPY", "IEF"],
    extend=True,
)
```

- The argument `rate_to_price=False` specifies that bond yield rates should not be converted to price values in the returned data:

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "Bonds-Daily-Price",
    ["US10Y"],
    rate_to_price=False,
)
```

- The argument `to_usd=False` indicates that the data should not be converted to U.S. dollars, implying that it might be available in another currency.

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "Indices-Daily-Price",
    ["US10Y"],
    to_usd=False,
)
```

### Backtest engine

The `pwb_toolbox.backtesting` module offers simple building blocks for running
Backtrader simulations. Alpha models generate insights which are turned
into portfolio weights and executed via Backtrader orders.

```python
from pwb_toolbox.backtesting.examples import GoldenCrossAlpha, EqualWeightPortfolio
from pwb_toolbox.backtesting import run_backtest
from pwb_toolbox.backtesting.execution_models import ImmediateExecutionModel
from pwb_toolbox.backtesting.risk_models import MaximumTotalPortfolioExposure
from pwb_toolbox.backtesting.universe_models import ManualUniverseSelectionModel

run_backtest(
    ManualUniverseSelectionModel(["SPY", "QQQ"]),
    GoldenCrossAlpha(),
    EqualWeightPortfolio(),
    execution=ImmediateExecutionModel(),
    risk=MaximumTotalPortfolioExposure(max_exposure=1.0),
    start="2015-01-01",
)
```

The backtesting package is composed of a few focused modules:

- `backtest_engine` – glue code that wires together universe selection,
  alpha models, portfolio construction and execution into a Backtrader run.
- `base_strategy` – common bookkeeping and helpers used by all provided
  strategies.
- `commission` – cost models for simulating broker commissions and spreads.
- `indicators` – reusable signal and technical indicator implementations.
- `optimization_engine` – genetic‑algorithm tooling for parameter searches.
- `portfolio` – utilities for combining the results of several strategies and
  producing performance reports.
- `strategies` – ready‑to‑use Backtrader `Strategy` subclasses.
- `universe` – helpers for building trading universes (e.g. most liquid symbols).


`pwb_toolbox.backtesting.strategies` ships a collection of portfolio templates
with different rebalancing rules and signal expectations:

- **DailyEqualWeightPortfolio** – holds all assets with a long signal and
  allocates equal weight each day.
- **DailyLeveragePortfolio** – goes long with fixed leverage when the signal is
  1 and is otherwise flat.
- **EqualWeightEntryExitPortfolio** – opens equally‑weighted positions when an
  entry condition triggers and leaves existing winners untouched.
- **DynamicEqualWeightPortfolio** – event‑driven equal‑weight portfolio that can
  rebalance on any signal change or only when the set of long assets changes.
- **MonthlyLongShortPortfolio** – once per month allocates half of the leverage
  to longs and half to shorts based on a universe‑aware signal.
- **MonthlyLongShortQuantilePortfolio** – monthly rebalance that ranks assets
  by a per‑asset signal and goes long the strongest and short the weakest.
- **MonthlyRankedEqualWeightPortfolio** – monthly equal‑weight portfolio with an
  optional ranking step and support for keeping only the top *N* assets.
- **QuarterlyTopMomentumPortfolio** – every quarter concentrates exposure in the
  single asset with the strongest recent momentum.
- **RollingSemesterLongShortPortfolio** – semi‑annual rebalancing template that
  accumulates long/short signals over six‑month windows.
- **WeeklyLongShortDecilePortfolio** – rebalances weekly and trades the top and
  bottom deciles of a signal distribution.
- **WeightedAllocationPortfolio** – turns user‑provided weights into integer
  share positions under a leverage constraint.

### Optimal Limit Order Execution

The module `pwb_toolbox.execution.optimal_limit_order` implements the optimal
limit‑order placement framework described in *Optimal Portfolio Liquidation with Limit Orders* by Guéant, Lehalle, and Tapia.
Given a target quantity and time horizon, `get_optimal_quote` solves the associated system of
differential equations to return the price offset from the mid‑price that
maximises the expected utility of execution. Market parameters such as
volatility (`sigma`), arrival rate of market orders (`A`), liquidity impact
(`k`), trader risk aversion (`gamma`) and liquidation penalty (`b`) can be
supplied to model different scenarios. Setting `is_plot=True` visualises the
optimal quote path over time.

### Live Strategy Execution

The execution helpers in `pwb_toolbox.execution` can connect to brokers to run
strategies in real time.  A typical session collects account information,
computes target positions and submits the necessary orders.

#### Interactive Brokers

```python
from pathlib import Path
import pandas as pd
from pwb_toolbox import execution as pwb_exec

STRATEGIES = {"my_strategy": {"path": "my_package.my_strategy", "weight": 1.0}}
logs_dir = Path("logs")
ACCOUNT_REFERENCE_NAV_VALUE = 100_000
ACCOUNT_REFERENCE_NAV_DATE = pd.Timestamp("2023-01-01")
LEVERAGE = 1.0
MARKET_DATA_TYPE = 1

ibc = pwb_exec.IBConnector(market_data_type=MARKET_DATA_TYPE)
ibc.connect()

account_nav_value = ibc.get_account_nav()
account_nav_date = pd.Timestamp.today().normalize()

nav_entry = pwb_exec.append_nav_history(logs_dir, account_nav_value)
nav_series, raw_positions = pwb_exec.run_strategies(STRATEGIES)
strategies_positions, theoretical_positions = pwb_exec.scale_positions(
    STRATEGIES,
    raw_positions,
    nav_series,
    ACCOUNT_REFERENCE_NAV_VALUE,
    LEVERAGE,
    ACCOUNT_REFERENCE_NAV_DATE,
)

ib_positions = ibc.get_positions()
orders = pwb_exec.compute_orders(theoretical_positions, ib_positions)

execution_time = 5 * 60  # five minutes
trades = pwb_exec.execute_and_log_orders(ibc, orders, execution_time)

pwb_exec.log_current_state(
    logs_dir,
    account_nav_value,
    strategies_positions,
    theoretical_positions,
    ib_positions,
    orders,
    account_nav_date,
    trades=trades,
    nav_history_entry=nav_entry,
)

ibc.disconnect()
```

#### CCXT Exchanges

```python
from pathlib import Path
import pandas as pd
from pwb_toolbox import execution as pwb_exec

STRATEGIES = {"my_strategy": {"path": "my_package.my_strategy", "weight": 1.0}}
logs_dir = Path("logs")
ACCOUNT_REFERENCE_NAV_VALUE = 100_000
ACCOUNT_REFERENCE_NAV_DATE = pd.Timestamp("2023-01-01")
LEVERAGE = 1.0

cc = pwb_exec.CCXTConnector(
    exchange="binance",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
)
cc.connect()

account_nav_value = cc.get_account_nav()
account_nav_date = pd.Timestamp.today().normalize()

nav_entry = pwb_exec.append_nav_history(logs_dir, account_nav_value)
nav_series, raw_positions = pwb_exec.run_strategies(STRATEGIES)
strategies_positions, theoretical_positions = pwb_exec.scale_positions(
    STRATEGIES,
    raw_positions,
    nav_series,
    ACCOUNT_REFERENCE_NAV_VALUE,
    LEVERAGE,
    ACCOUNT_REFERENCE_NAV_DATE,
)

cc_positions = cc.get_positions()
orders = pwb_exec.compute_orders(theoretical_positions, cc_positions)

execution_time = 5 * 60
trades = pwb_exec.execute_and_log_orders(cc, orders, execution_time)

pwb_exec.log_current_state(
    logs_dir,
    account_nav_value,
    strategies_positions,
    theoretical_positions,
    cc_positions,
    orders,
    account_nav_date,
    trades=trades,
    nav_history_entry=nav_entry,
)

cc.disconnect()
```

### Performance Analysis

After running a live trading session, you can analyze the returned equity series using the
`pwb_toolbox.performance` module.

```python
from pwb_toolbox.backtesting.examples import GoldenCrossAlpha, EqualWeightPortfolio
from pwb_toolbox.backtesting import run_backtest
from pwb_toolbox.backtesting.execution_models import ImmediateExecutionModel
from pwb_toolbox.performance import total_return, cagr
from pwb_toolbox.performance.plots import plot_equity_curve

result, equity = run_backtest(
    ManualUniverseSelectionModel(["SPY", "QQQ"]),
    GoldenCrossAlpha(),
    EqualWeightPortfolio(),
    execution=ImmediateExecutionModel(),
    start="2015-01-01",
)

print("Total return:", total_return(equity))
print("CAGR:", cagr(equity))

plot_equity_curve(equity)
```

## Contributing

Contributions to the `pwb-toolbox` package are welcome! If you have any improvements, new datasets, or strategy ideas to share, please follow these guidelines:

1. Fork the repository and create a new branch for your feature.
2. Make your changes and ensure they adhere to the package's coding style.
3. Write tests to validate the functionality or provide sample usage examples.
4. Submit a pull request, clearly explaining the purpose and benefits of your contribution.

Please note that all contributions are subject to review and approval by the maintainers.

### Build the Package

To build the package, run:

```bash
python -m pip install --upgrade build
rm -r dist
python -m build
```

To upload the package to PyPI, run:

```bash
twine upload dist/*
```

## Contact

For any questions, issues, or suggestions regarding the `pwb-toolbox` package, please contact the maintainers or create an issue on the repository. We appreciate your feedback and involvement in improving the package.
Happy trading!
