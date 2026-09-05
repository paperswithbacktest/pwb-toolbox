# pwb-toolbox

The `pwb-toolbox` package provides tools and resources for systematic trading
strategies. It bundles datasets, backtesting helpers, performance analytics and
execution connectors to help you develop and evaluate trading algorithms.

## Installation

```bash
pip install pwb-toolbox
```

This package requires Python 3.10 or higher.

To use PWB datasets, supply a Papers With Backtest API key via the `PWB_API_KEY`
environment variable. When it is set, `load_dataset` downloads parquet shards
directly from the PWB API. Without an API key, log in to the Hugging Face Hub
(where public PWB datasets are hosted) instead:

```bash
huggingface-cli login
```

## Quick start

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.get_pricing(["AAPL", "MSFT", "GOOGL"])
df = pwb_ds.load_dataset("Stocks-Daily-Price")
```

## Contents

```{toctree}
:maxdepth: 2

datasets
backtesting
execution
```

## Links

- [Source code](https://github.com/paperswithbacktest/pwb-toolbox)
- [Papers With Backtest](https://paperswithbacktest.com)
