"""
Timeseries daily from Yahoo Finance.
"""

from datetime import datetime

from datasets import load_dataset
import pandas as pd
import requests
import time
from tqdm import tqdm

from timeseries_daily import TimeseriesDaily


class TimeseriesDailyYF(TimeseriesDaily):
    """
    Timeseries daily from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"timeseries-daily-{self.suffix}"

    def get_timeseries_daily(self, ticker: str):
        from_timestamp = int(datetime.timestamp(datetime(1980, 1, 1)))
        to_timestamp = int(datetime.timestamp(datetime.now()))
        url = f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}?period1={from_timestamp}&period2={to_timestamp}&interval=1d&events=history&includeAdjustedClose=true"
        df = pd.read_csv(url)
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        return df

    def download(self):
        """
        Download the daily data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            df = self.get_timeseries_daily(ticker)
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


def main():
    """
    Main function.
    """
    timeseries_daily_yf = TimeseriesDailyYF()
    timeseries_daily_yf.crawl()


if __name__ == "__main__":
    main()
