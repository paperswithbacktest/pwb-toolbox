# Datasets

## List of datasets

| **Dataset Name** | **URL** | **Description** |
|------------------|---------|-----------------|
| All Daily News | [https://paperswithbacktest.com/datasets/all-daily-news](https://paperswithbacktest.com/datasets/all-daily-news) | Daily aggregated financial and macroeconomic news feed. Useful for sentiment analysis and event-driven strategies. |
| Bonds Daily Price | [https://paperswithbacktest.com/datasets/bonds-daily-price](https://paperswithbacktest.com/datasets/bonds-daily-price) | Historical daily bond price data across government and corporate bonds. |
| Commodities Daily Price | [https://paperswithbacktest.com/datasets/commodities-daily-price](https://paperswithbacktest.com/datasets/commodities-daily-price) | Daily price data for major commodities such as oil, gold, and agricultural products. |
| Cryptocurrencies Daily Price | [https://paperswithbacktest.com/datasets/cryptocurrencies-daily-price](https://paperswithbacktest.com/datasets/cryptocurrencies-daily-price) | Historical daily prices for major cryptocurrencies. |
| ETFs Daily Price | [https://paperswithbacktest.com/datasets/etfs-daily-price](https://paperswithbacktest.com/datasets/etfs-daily-price) | Daily closing prices of exchange-traded funds (ETFs) globally. |
| Forex Daily Price | [https://paperswithbacktest.com/datasets/forex-daily-price](https://paperswithbacktest.com/datasets/forex-daily-price) | Daily foreign exchange rates between major and emerging market currencies. |
| Indices Daily Price | [https://paperswithbacktest.com/datasets/indices-daily-price](https://paperswithbacktest.com/datasets/indices-daily-price) | Historical daily prices for global stock market indices. |
| Stocks 1-Min Price | [https://paperswithbacktest.com/datasets/stocks-1min-price](https://paperswithbacktest.com/datasets/stocks-1min-price) | Intraday 1-minute price data for major equities. Ideal for high-frequency or intraday backtests. |
| Stocks Daily Price | [https://paperswithbacktest.com/datasets/stocks-daily-price](https://paperswithbacktest.com/datasets/stocks-daily-price) | Historical daily stock price dataset covering global exchanges. |
| Stocks Quarterly Balance Sheet | [https://paperswithbacktest.com/datasets/stocks-quarterly-balancesheet](https://paperswithbacktest.com/datasets/stocks-quarterly-balancesheet) | Company-level quarterly balance sheet fundamentals. |
| Stocks Quarterly Cash Flow | [https://paperswithbacktest.com/datasets/stocks-quarterly-cashflow](https://paperswithbacktest.com/datasets/stocks-quarterly-cashflow) | Company-level quarterly cash flow statements. |
| Stocks Quarterly Earnings | [https://paperswithbacktest.com/datasets/stocks-quarterly-earnings](https://paperswithbacktest.com/datasets/stocks-quarterly-earnings) | Quarterly earnings reports and EPS data. |
| Stocks Quarterly Income Statement | [https://paperswithbacktest.com/datasets/stocks-quarterly-incomestatement](https://paperswithbacktest.com/datasets/stocks-quarterly-incomestatement) | Quarterly income statements providing revenue, expenses, and profit metrics. |
| Best Alternative Data | [https://paperswithbacktest.com/datasets/best-alternative-data](https://paperswithbacktest.com/datasets/best-alternative-data) | Curated collection of alternative datasets (e.g., sentiment, macro signals, ESG metrics). |

## Arguments

Load daily stock price data for specific symbols using the load_dataset function. The first call retrieves data for Apple and Microsoft. The second call retrieves the same stocks but without price adjustments (`adjust=False`). The third call loads daily price data for the S&P 500 index:

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

The `extend=True` argument instructs the function to return an extended historical data using indices, commodities, and bonds data.

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "ETFs-Daily-Price",
    ["SPY", "IEF"],
    extend=True,
)
```

The argument `rate_to_price=False` specifies that bond yield rates should not be converted to price values in the returned data:

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "Bonds-Daily-Price",
    ["US10Y"],
    rate_to_price=False,
)
```

The argument `to_usd=False` indicates that the data should not be converted to U.S. dollars, implying that it might be available in another currency.

```python
import pwb_toolbox.datasets as pwb_ds

df = pwb_ds.load_dataset(
    "Indices-Daily-Price",
    ["US10Y"],
    to_usd=False,
)
```