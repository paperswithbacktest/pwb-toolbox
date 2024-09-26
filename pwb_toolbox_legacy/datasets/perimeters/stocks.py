from datetime import date
import json

from datasets import load_dataset
import pandas as pd
import requests

from pwb_toolbox.helpers import nasdaq_headers, retry_get
from pwb_toolbox.datasets.perimeters import Perimeter


class Stocks(Perimeter):
    def __init__(self, tag_date: date = None, username: str = None):
        super().__init__("stocks", tag_date, username)
        self.name = f"perimeter-stocks"

    def __download_nasdaq(self) -> pd.DataFrame:
        """
        Returns a DataFrame of NASDAQ stocks
        """
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"
        response = retry_get(url, headers=nasdaq_headers(), mode="curl")
        json_data = response.json()
        df = pd.DataFrame(data=json_data["data"]["rows"])
        has_market_cap = (
            (df.country != "") & (df.marketCap != "") & (df.marketCap != "0.00")
        )
        df = df.loc[has_market_cap, :]
        df.sort_values(
            by=["marketCap"], inplace=True, ascending=False
        )  # sorted by crawling priority
        df = df[["symbol", "name", "sector", "industry"]]
        # filter common stocks
        index = df.name.apply(lambda x: x.endswith("Common Stock"))
        df = df.loc[index, :]
        df.reset_index(drop=True, inplace=True)
        nasdaq_names = df.name.apply(
            lambda x: x.replace(" Common Stock", "")
            .replace(" Inc.", "")
            .replace(" Inc", "")
            .replace(" Class A", "")
        )
        df.name = nasdaq_names
        df.rename(
            columns={
                "name": "security",
                "sector": "gics_sector",
                "industry": "gics_sub_industry",
            },
            inplace=True,
        )
        return df

    def __download_sp500(self) -> pd.DataFrame:
        dataset = load_dataset("paperswithbacktest/perimeter-sp500")
        df = dataset["train"].to_pandas()
        df = df[["symbol", "security", "gics_sector", "gics_sub_industry"]]
        return df

    def __download(self) -> pd.DataFrame:
        self.dataset_df = pd.concat(
            [
                self.__download_sp500(),
                self.__download_nasdaq(),
            ]
        )  # sorted by crawling priority
        self.dataset_df = self.dataset_df.drop_duplicates(
            subset=["symbol"], keep="first"
        )
        max_number_of_stocks = 1500
        self.dataset_df = self.dataset_df.head(max_number_of_stocks)
        self.dataset_df.reset_index(drop=True, inplace=True)

    def set_dataset_df(self):
        """
        Frames to dataset.
        """
        self.__download()
