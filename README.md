<div align="center">
  <img src="static/images/systematic-trading.jpeg" height=200 alt=""/>
  <h1>Papers With Backtest Toolbox</h1>
</div>

The `pwb-toolbox` package is designed to provide tools and resources for systematic trading strategies. It includes datasets and strategy ideas to assist in developing and backtesting trading algorithms. For detailed instructions on how to use this package effectively, please refer to the associated website by visiting: https://paperswithbacktest.com/.


## Installation

To install the pwb-toolbox package:

```bash
pip install pwb-toolbox
```
This package requires Python 3.10 or higher.

To use PWB datasets, you need to login to Huggingface Hub (where PWB datasets are hosted) with Access Token:

```bash
huggingface-cli login
```

## Usage

The `pwb-toolbox` package offers a range of functionalities for systematic trading analysis. Here are some examples of how to utilize the package:

### Datasets

The `pwb_toolbox.datasets` module offers to load datasets for different asset classes, such as bonds, commodities, cryptocurrencies, ETFs, forex, indices, and stocks, using the `get_pricing` or the `load_dataset` functions:

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

For more, see [docs/datasets.md](/docs/datasets.md).


### Backtest engine

The `pwb_toolbox.backtesting` module offers simple building blocks for running
Backtrader simulations. Alpha models generate insights which are turned
into portfolio weights and executed via Backtrader orders.

```python
import numpy as np
import backtrader as bt
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds


# ────────────────────────────────────────────────────────────────
# 1.  SIGNAL
# ----------------------------------------------------------------
class DualMomentumSignal(bt.Indicator):
    """
    Per‑asset momentum signal (12‑month Rate‑of‑Change) plus a helper
    that the portfolio can call to obtain the whole allocation vector
    for the *current* bar.
    """

    lines = ("momentum",)
    params = (("period", 252),)  # ≈12 months of trading days

    def __init__(self):
        # Rate‑of‑Change over the period (use adjusted prices if your feed provides them)
        self.lines.momentum = bt.indicators.RateOfChange(
            self.data.close, period=self.p.period
        )

    # ----- helper ------------------------------------------------
    @staticmethod
    def build_weights(
        momentum_now: dict,
        asset_groups: list[list[str]],
        treasury_bill: str,
        momentum_threshold: float,
        leverage: float,
    ) -> dict[str, float]:
        """
        Returns dict {symbol: target weight}.  Weights sum to *leverage*.

        Implements *dual momentum* per Antonacci:
        pick the RS winner in each module *and* require its lookback return
        to exceed the T‑bill lookback return; otherwise allocate that module to T‑bills.
        """
        longs: list[str] = []
        tbill_slots = 0

        # dynamic absolute momentum hurdle = T‑bill momentum (fallback to provided threshold if NaN)
        tbill_mom = momentum_now.get(treasury_bill, np.nan)
        abs_hurdle = tbill_mom if not np.isnan(tbill_mom) else momentum_threshold

        # 1) Select the best performer in each group (relative momentum) with absolute check vs T‑bill
        for group in asset_groups:
            # Skip this group if any of its assets' momentum is still NaN
            if any(np.isnan(momentum_now.get(s, np.nan)) for s in group):
                continue

            perf_vals = [momentum_now[s] for s in group]
            max_perf = max(perf_vals)
            max_symb = group[perf_vals.index(max_perf)]

            if max_perf > abs_hurdle:
                longs.append(max_symb)
            else:
                tbill_slots += 1

        traded_slots = len(longs) + tbill_slots
        if traded_slots == 0:
            # Nothing to trade yet (e.g., early look‑back period)
            return {}

        # 2) Equal‑weight the *slots*; each module contributes exactly one slot
        slot_wt = leverage / traded_slots
        weights = {symb: slot_wt for symb in longs}

        if tbill_slots:
            weights[treasury_bill] = slot_wt * tbill_slots

        return weights


# ────────────────────────────────────────────────────────────────
# 2.  MONTHLY PORTFOLIO
# ----------------------------------------------------------------
class MonthlyDualMomentumPortfolio(pwb_bt.BaseStrategy):
    """
    Generic monthly rebalancing engine that asks the signal for a
    *dict of target weights* and then places the necessary orders.
    """

    params = (
        ("leverage", 0.9),
        ("period", 252),
        ("momentum_threshold", 0.0),
        ("asset_groups", None),  # list of lists (set below)
        ("treasury_bill", "BIL"),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),  # kwargs forwarded to signal
    )

    def __init__(self):
        super().__init__()
        # build signals
        self.sig = {
            d._name: self.p.indicator_cls(d, period=self.p.period) for d in self.datas
        }
        self.last_month = -1

    # ----- helper ------------------------------------------------
    def _current_weights(self, use_prev_bar: bool = False) -> dict[str, float]:
        """
        Compute weight dict using momentum readings.
        If use_prev_bar=True, take momentum from [-1] (prior bar), which is what we want
        on the first bar of a new month to mimic 'month-end signal, trade next month'.
        """
        idx = -1 if use_prev_bar else 0
        momentum_now = {symb: self.sig[symb][idx] for symb in self.sig}
        return self.p.indicator_cls.build_weights(
            momentum_now=momentum_now,
            asset_groups=self.p.asset_groups,
            treasury_bill=self.p.treasury_bill,
            momentum_threshold=self.p.momentum_threshold,
            leverage=self.p.leverage,
        )

    # ----- main step --------------------------------------------
    def next(self):
        super().next()
        today = self.datas[0].datetime.date(0)
        if today.month == self.last_month:
            return  # only once per month
        self.last_month = today.month

        # Use prior bar's momentum when the month flips (month-end signal, trade next bar)
        tgt_wt = self._current_weights(use_prev_bar=True)

        # 1) Flatten anything that should now be zero.
        for d in self.datas:
            if d._name not in tgt_wt or tgt_wt[d._name] == 0:
                self.order_target_percent(d, target=0.0)

        # 2) Set targets for active assets
        for d in self.datas:
            wt = tgt_wt.get(d._name, 0.0)
            if wt != 0 and self.is_tradable(d):
                self.order_target_percent(d, target=wt)


def run_strategy():
    symbols = ["SPY", "EFA", "HYG", "LQD", "REM", "VNQ", "TLT", "GLD", "BIL"]

    strategy = pwb_bt.run_strategy(
        indicator_cls=DualMomentumSignal,  # per‑asset indicator
        indicator_kwargs={"period": 252},
        strategy_cls=MonthlyDualMomentumPortfolio,
        strategy_kwargs={
            "asset_groups": [
                ["SPY", "EFA"],  # equities: US vs EAFE+
                ["HYG", "LQD"],  # credit risk: high yield vs credit
                ["VNQ", "REM"],  # REITs: equity REIT vs mortgage REIT (per paper)
                ["TLT", "GLD"],  # economic stress: Treasuries vs gold
            ],
            "leverage": 0.9,
        },
        symbols=symbols,
        start_date="1990-01-01",
        cash=100_000.0,
    )
    return strategy


if __name__ == "__main__":
    strategy = run_strategy()
```

For more, see [docs/backtesting.md](/docs/backtesting.md).



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

## PWB Server

```bash
cd pwb-toolbox/server
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
