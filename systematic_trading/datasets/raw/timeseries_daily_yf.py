"""
Timeseries daily from Yahoo Finance.
"""

from datetime import datetime
import urllib
import time

from datasets import load_dataset
import pandas as pd
import requests
from tqdm import tqdm

from systematic_trading.datasets.raw.timeseries_daily import TimeseriesDaily


class TimeseriesDailyYF(TimeseriesDaily):
    """
    Timeseries daily from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"timeseries-daily-{self.suffix}"

    def __read_csv_with_retry(url, retries=5, wait_time=5):
        for i in range(retries):
            try:
                df = pd.read_csv(url)
                return df
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    print(
                        "HTTP Error 503: Service Unavailable. Retrying in {} seconds...".format(
                            wait_time
                        )
                    )
                    time.sleep(wait_time)
                else:
                    raise
        # If all retries fail
        print("Unable to fetch data after {} retries.".format(retries))
        return None

    def __get_timeseries_daily(self, ticker: str):
        from_timestamp = int(datetime.timestamp(datetime(1980, 1, 1)))
        to_timestamp = int(datetime.timestamp(datetime.now()))
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}?period1={from_timestamp}&period2={to_timestamp}&interval=1d&events=history&includeAdjustedClose=true"
        df = pd.read_csv(url)
        df["Date"] = pd.to_datetime(df["Date"]).dt.date.apply(lambda x: x.isoformat())
        return df

    def __get_timeseries_daily_with_retry(self, ticker: str):
        retries = 5
        wait_time = 5
        for i in range(retries):
            try:
                df = self.__get_timeseries_daily(ticker)
                return df
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    print(
                        "HTTP Error 503: Service Unavailable. Retrying in {} seconds...".format(
                            wait_time
                        )
                    )
                    sleep(wait_time)
                else:
                    raise
        print("Unable to fetch data after {} retries.".format(retries))
        return None

    def build(self):
        """
        Download the daily data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            df = self.__get_timeseries_daily_with_retry(ticker)
            if df is None:
                continue
            df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                },
                inplace=True,
            )
            df["symbol"] = symbol
            # use reindex() to set 'symbol' as the first column
            df = df.reindex(columns=["symbol"] + list(df.columns[:-1]))
            frames.append(df)
            time.sleep(self.sleep_time)
        self.data = pd.concat(frames)
        self.data.sort_values(by=["symbol", "date"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)
