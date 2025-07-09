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

To login to Huggingface Hub with Access Token

```bash
huggingface-cli login
```

## Usage

The `pwb-toolbox` package offers a range of functionalities for systematic trading analysis. Here are some examples of how to utilize the package:

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

## Backtest engine

The `pwb_toolbox.backtest` module offers simple building blocks for running
Backtrader simulations. Alpha models generate `Insight` objects which are turned
into portfolio weights and executed via Backtrader orders.

```python
from pwb_toolbox.backtest.examples import GoldenCrossAlpha, EqualWeightPortfolio
from pwb_toolbox.backtest import run_backtest

run_backtest(["SPY", "QQQ"], GoldenCrossAlpha(), EqualWeightPortfolio(), start="2015-01-01")
```

## Contributing

Contributions to the `pwb-toolbox` package are welcome! If you have any improvements, new datasets, or strategy ideas to share, please follow these guidelines:

1. Fork the repository and create a new branch for your feature.
2. Make your changes and ensure they adhere to the package's coding style.
3. Write tests to validate the functionality or provide sample usage examples.
4. Submit a pull request, clearly explaining the purpose and benefits of your contribution.

Please note that all contributions are subject to review and approval by the maintainers.

## Build the Package

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

## License

The `pwb-toolbox` package is released under the MIT license. See the LICENSE file for more details.

## Contact

For any questions, issues, or suggestions regarding the `pwb-toolbox` package, please contact the maintainers or create an issue on the repository. We appreciate your feedback and involvement in improving the package.
Happy trading!
