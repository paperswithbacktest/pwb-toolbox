<div align="center">
  <img src="static/images/systematic-trading.jpeg" height=200 alt=""/>
  <h1>Papers With Backtest Toolbox</h1>
</div>

The `pwb-toolbox` package is designed to provide tools and resources for systematic trading strategies. It includes datasets and strategy ideas to assist in developing and backtesting trading algorithms.


## Installation

To install the pwb-toolbox package:

```bash
pip install pwb-toolbox
```
This package requires Python 3.10 or higher.

To use PWB datasets, you can supply a Papers With Backtest API key via the `PWB_API_KEY` environment variable. When that is set,
`load_dataset` will download parquet shards directly from the PWB API. If no API key is available, you can instead login to the
Huggingface Hub (where public PWB datasets are hosted) with an access token:

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


### Backtesting

The `pwb_toolbox.backtesting` module offers simple building blocks for running Backtrader simulations.

Here is a strategy example:

```python
import numpy as np
import backtrader as bt
import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.datasets as pwb_ds


# ────────────────────────────────────────────────────────────────
# Toy dual-momentum: each month hold SPY if its lookback return > T-bill,
# otherwise sit in BIL. Kept minimal while using pwb_bt & pwb_ds.
# ────────────────────────────────────────────────────────────────

class SimpleMomentum(bt.Indicator):
    """12-month rate of change on close."""
    lines = ("roc",)
    params = (("period", 252),)

    def __init__(self):
        self.lines.roc = bt.indicators.RateOfChange(self.data.close, period=self.p.period)


class MonthlySwitcher(pwb_bt.BaseStrategy):
    params = dict(
        period=252,            # ~12 months
        risky="SPY",
        safe="BIL",
        leverage=1.0,
    )

    def __init__(self):
        super().__init__()
        # Attach momentum indicators to each data feed
        self.mom = {d._name: SimpleMomentum(d, period=self.p.period) for d in self.datas}
        self._last_month = -1

    def next(self):
        super().next()

        # Rebalance only on month change
        today = self.datas[0].datetime.date(0)
        if today.month == self._last_month:
            return
        self._last_month = today.month

        # Use prior bar to emulate "signal at month-end, trade next month"
        idx = -1
        spy_m = float(self.mom[self.p.risky].roc[idx])
        bil_m = float(self.mom[self.p.safe].roc[idx])

        # Decide allocation
        hold_risky = (not np.isnan(spy_m)) and (not np.isnan(bil_m)) and (spy_m > bil_m)

        targets = {
            self.p.risky: self.p.leverage if hold_risky else 0.0,
            self.p.safe:  0.0 if hold_risky else self.p.leverage,
        }

        # Set portfolio targets
        for d in self.datas:
            self.order_target_percent(d, targets.get(d._name, 0.0))


def run_strategy():
    # Minimal universe fetched via pwb_ds inside pwb_bt
    symbols = ["SPY", "BIL"]

    result = pwb_bt.run_strategy(
        indicator_cls=SimpleMomentum,             # kept for compatibility, but not required externally
        indicator_kwargs={"period": 252},
        strategy_cls=MonthlySwitcher,
        strategy_kwargs={"period": 252, "risky": "SPY", "safe": "BIL", "leverage": 1.0},
        symbols=symbols,
        start_date="2005-01-01",
        cash=100_000.0,
    )
    return result


if __name__ == "__main__":
    run_strategy()
```

To explore more, you can find over **140 strategy examples** at [https://paperswithbacktest.com/strategies](https://paperswithbacktest.com/strategies)).

For more about backtesting, see [docs/backtesting.md](/docs/backtesting.md).


### Execution

The execution helpers in `pwb_toolbox.execution` can connect to brokers to run
strategies in real time.  A typical session collects account information,
computes target positions and submits the necessary orders.

Two brokers are supporter today:

- Interactive Brokers
- CCXT (crypto)

For more about execution, see [docs/execution.md](/docs/execution.md).


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

## Tools

### Interactive Brokers server

To trade PWB strategies live with Interactive Brokers, you can use `pwb-toolbox/tools/ib_server`.

On a ubuntu server (for instance from https://www.ovhcloud.com/), install [Miniconda](https://www.anaconda.com/), [IB TWS](https://www.interactivebrokers.com/), and RDP with:

```bash
cd pwb-toolbox/tools/ib_server
./install.sh
conda activate pwb
```

If TWS is already started:

```bash
PWB_API_KEY="" python -m execute_meta_strategy
```

If TWS isn'y already started:

```bash
TWS_USERNAME="" TWS_PASSWORD="" python -m launch_ib && PWB_API_KEY="" python -m execute_meta_strategy
```

And to run the strategy daily, define the environment variables in `.bashrc` and then set up the following cron:

```bash
30 9 * * Mon-Fri /bin/bash /path/to/run_daily.sh >> /path/to/logfile 2>&1
```

To get logs:

```bash
python -m monitor --logs-dir $HOME/pwb-data/ib/execution_logs
```


NB: Fix to restart the desktop environment:

```bash
ps aux | grep xfce4
sudo pkill -u ubuntu
```


## Contributing

Contributions to the `pwb-toolbox` package are welcome! If you have any improvements, new datasets, or strategy ideas to share, please follow these guidelines:

1. Fork the repository and create a new branch for your feature.
2. Make your changes and ensure they adhere to the package's coding style.
3. Write tests to validate the functionality or provide sample usage examples.
4. Submit a pull request, clearly explaining the purpose and benefits of your contribution.

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
