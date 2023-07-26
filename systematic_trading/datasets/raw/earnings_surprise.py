"""
Earnings surprise from Nasdaq.
"""

from datetime import date, datetime
import time
import urllib

from datasets import load_dataset
import pandas as pd
import requests

from systematic_trading.datasets.raw import Raw
from systematic_trading.helpers import nasdaq_headers, retry_get


class EarningsSurprise(Raw):
    """
    Earnings surprise from Nasdaq.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"earnings-surprise-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "id",
            "fiscal_qtr_end",
            "date_reported",
            "eps",
            "consensus_forecast",
            "percentage_surprise",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def append_frame(self, symbol: str):
        ticker = self.symbol_to_ticker(symbol)
        url = f"https://api.nasdaq.com/api/company/{ticker}/earnings-surprise"
        response = retry_get(url, headers=nasdaq_headers(), mode="curl")
        json_data = response.json()
        if json_data["data"] is None:
            self.frames[symbol] = None
            return
        earnings_surprise = json_data["data"]["earningsSurpriseTable"]
        if earnings_surprise is None:
            self.frames[symbol] = None
            return
        df = pd.DataFrame(data=earnings_surprise["rows"])
        df.rename(
            columns={
                "fiscalQtrEnd": "fiscal_qtr_end",
                "dateReported": "date_reported",
                "consensusForecast": "consensus_forecast",
                "percentageSurprise": "percentage_surprise",
            },
            inplace=True,
        )
        df["date_reported"] = pd.to_datetime(df["date_reported"])
        df["id"] = range(len(df))
        df["symbol"] = symbol
        df["date"] = self.tag_date.isoformat()
        df = df.reindex(columns=self.expected_columns)
        self.frames[symbol] = df

    def set_dataset_df(self):
        self.dataset_df = pd.concat([f for f in self.frames.values() if f is not None])
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "date", "id"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)


if __name__ == "__main__":
    symbol = "AAPL"
    suffix = "stocks"
    tag_date = datetime(2023, 5, 26).date()
    username = "edarchimbaud"
    dataset = EarningsSurprise(suffix=suffix, tag_date=tag_date, username=username)
    dataset.append_frame(symbol)
