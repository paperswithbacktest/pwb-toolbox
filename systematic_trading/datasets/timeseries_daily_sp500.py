"""
Daily S&P 500 data.
"""

from datasets import load_dataset
import pandas as pd
import re
from tqdm import tqdm
import yfinance as yf

from timeseries_daily import TimeseriesDaily


class TimeseriesDailySP500(TimeseriesDaily):
    def __init__(self):
        super().__init__()
        self.name = "timeseries-daily-sp500"

    def __symbol_to_ticker(self, symbol: str):
        pattern = re.compile(r"\.B$")
        return pattern.sub("-B", symbol)

    def download(self):
        """
        Download the daily S&P 500 data from Yahoo Finance.
        """
        dataset = load_dataset("edarchimbaud/index-constituents-sp500")
        frames = []
        for symbol in tqdm(dataset["train"]["symbol"]):
            ticker = self.__symbol_to_ticker(symbol)
            instrument = yf.Ticker(ticker)
            df = instrument.history(period="max")
            error_message = yf.shared._ERRORS.get(ticker)
            if error_message is not None:
                print(error_message)
                break
            df.reset_index(drop=False, inplace=True)
            df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                    "Dividends": "dividends",
                    "Stock Splits": "stock_splits",
                },
                inplace=True,
            )
            df["symbol"] = symbol
            # use reindex() to set 'symbol' as the first column
            df = df.reindex(columns=["symbol"] + list(df.columns[:-1]))
            df.reset_index(drop=True, inplace=True)
            frames.append(df)
        self.data = pd.concat(frames)
        self.data.sort_values(by=["symbol", "date"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    timeseries_daily_sp500 = TimeseriesDailySP500()
    timeseries_daily_sp500.download()
    timeseries_daily_sp500.to_hf_datasets()


if __name__ == "__main__":
    main()
