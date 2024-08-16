"""
Timeseries 1mn from Yahoo Finance.
"""

from datetime import date, datetime
import time
import urllib

from datasets import load_dataset
import pandas as pd
import requests

from systematic_trading.datasets.raw import Raw
from systematic_trading.helpers import retry_get


class Timeseries1mn(Raw):
    """
    Timeseries 1mn from Yahoo Finance.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"timeseries-1m-{suffix}"
        self.expected_columns = [
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def append_frame(self, symbol: str):
        ticker = self.symbol_to_ticker(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?region=US&lang=en-US&includePrePost=false&interval=1m&useYfid=true&range=1d&corsDomain=finance.yahoo.com&.tsrc=finance"
        try:
            response = retry_get(url)
        except:
            self.frames[symbol] = None
            return
        json_data = response.json()
        result = json_data["chart"]["result"][0]
        if "timestamp" not in result:
            self.frames[symbol] = None
            return
        timestamp = result["timestamp"]
        indicators = result["indicators"]["quote"][0]
        data = {"datetime": [datetime.fromtimestamp(t) for t in timestamp]}
        data.update(indicators)
        df = pd.DataFrame(data=data)
        df["symbol"] = symbol
        df = df.reindex(columns=self.expected_columns)
        self.frames[symbol] = df

    def set_dataset_df(self):
        self.dataset_df = pd.concat([f for f in self.frames.values() if f is not None])
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "datetime"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)


if __name__ == "__main__":
    symbol = "AAPL"
    suffix = "stocks"
    tag_date = datetime(2023, 5, 26).date()
    username = "edarchimbaud"
    dataset = Timeseries1mn(suffix=suffix, tag_date=tag_date, username=username)
    dataset.append_frame(symbol)
