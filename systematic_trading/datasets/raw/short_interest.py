"""
Short interest from Nasdaq.
"""

from datetime import date, datetime
import time
import urllib

from datasets import load_dataset
import numpy as np
import pandas as pd
import requests

from systematic_trading.datasets.raw import Raw
from systematic_trading.helpers import retry_get


class ShortInterest(Raw):
    """
    Short interest from Nasdaq.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"short-interest-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "id",
            "settlement_date",
            "interest",
            "avg_daily_share_volume",
            "days_to_cover",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def append_frame(self, symbol: str):
        ticker = self.symbol_to_ticker(symbol)
        url = f"https://api.nasdaq.com/api/quote/{ticker}/short-interest?assetClass=stocks"
        headers = {
            "authority": "api.nasdaq.com",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.5",
            "cache-control": "max-age=0",
            "sec-ch-ua": '"Brave";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "sec-gpc": "1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        }
        response = retry_get(url, headers=headers, mode="curl")
        json_data = response.json()
        if json_data["data"] is None:
            return
        short_interest_table = json_data["data"]["shortInterestTable"]
        if short_interest_table is None:
            return
        data = short_interest_table["rows"]
        df = pd.DataFrame(data=data)
        df["settlementDate"] = pd.to_datetime(df["settlementDate"])
        df["interest"] = df["interest"].apply(
            lambda x: int(x.replace(",", "")) if x != "N/A" else None
        )
        df["avgDailyShareVolume"] = df["avgDailyShareVolume"].apply(
            lambda x: int(x.replace(",", "")) if x != "N/A" else None
        )
        df.rename(
            columns={
                "settlementDate": "settlement_date",
                "avgDailyShareVolume": "avg_daily_share_volume",
                "daysToCover": "days_to_cover",
            },
            inplace=True,
        )
        df["id"] = range(len(df))
        df["symbol"] = symbol
        df["date"] = self.tag_date.isoformat()
        df = df.reindex(columns=self.expected_columns)
        self.frames[symbol] = df

    def set_dataset_df(self):
        self.dataset_df = pd.concat(self.frames.values())
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "date", "id"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)


if __name__ == "__main__":
    symbol = "AAPL"
    suffix = "sp500"
    tag_date = datetime(2023, 5, 26).date()
    username = "edarchimbaud"
    dataset = ShortInterest(suffix=suffix, tag_date=tag_date, username=username)
    dataset.append_frame(symbol)
