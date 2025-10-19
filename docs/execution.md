# Execution

## Interactive Brokers


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

## CCXT Exchanges

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

## Optimal Limit Order

The module `pwb_toolbox.execution.optimal_limit_order` implements the optimal
limit‑order placement framework described in [Optimal Portfolio Liquidation with Limit Orders](https://arxiv.org/abs/1106.3279) by Guéant, Lehalle, and Tapia.


Given a target quantity and time horizon, `get_optimal_quote` solves the associated system of
differential equations to return the price offset from the mid‑price that
maximises the expected utility of execution. Market parameters such as
volatility (`sigma`), arrival rate of market orders (`A`), liquidity impact
(`k`), trader risk aversion (`gamma`) and liquidation penalty (`b`) can be
supplied to model different scenarios. Setting `is_plot=True` visualises the
optimal quote path over time.