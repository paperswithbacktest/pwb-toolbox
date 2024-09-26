"""
Earnings forecast from Nasdaq.
"""

from datetime import date, datetime
import time
import urllib

from datasets import load_dataset
import pandas as pd
import requests

from pwb_toolbox.datasets.raw import Raw
from pwb_toolbox.helpers import nasdaq_headers, retry_get


class EarningsForecast(Raw):
    """
    Earnings forecast from Nasdaq.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"earnings-forecast-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "id",
            "fiscal_end",
            "consensus_eps_forecast",
            "high_eps_forecast",
            "low_eps_forecast",
            "no_of_estimates",
            "up",
            "down",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def append_frame(self, symbol: str):
        ticker = self.symbol_to_ticker(symbol)
        url = f"https://api.nasdaq.com/api/analyst/{ticker}/earnings-forecast"
        try:
            response = retry_get(url, headers=nasdaq_headers(), mode="curl")
        except:
            self.frames[symbol] = None
            return
        json_data = response.json()
        if json_data["data"] is None:
            self.frames[symbol] = None
            return
        quarterly_forecast = json_data["data"]["quarterlyForecast"]
        if quarterly_forecast is None:
            self.frames[symbol] = None
            return
        df = pd.DataFrame(data=quarterly_forecast["rows"])
        df.rename(
            columns={
                "fiscalEnd": "fiscal_end",
                "consensusEPSForecast": "consensus_eps_forecast",
                "highEPSForecast": "high_eps_forecast",
                "lowEPSForecast": "low_eps_forecast",
                "noOfEstimates": "no_of_estimates",
            },
            inplace=True,
        )
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
    username = "paperswithbacktest"
    dataset = EarningsForecast(suffix=suffix, tag_date=tag_date, username=username)
    dataset.append_frame(symbol)
