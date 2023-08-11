from datetime import date
import json

from datasets import load_dataset
import pandas as pd
import requests

from systematic_trading.helpers import nasdaq_headers
from systematic_trading.datasets.index_constituents import IndexConstituents


class Stocks(IndexConstituents):
    def __init__(self, tag_date: date = None, username: str = None):
        super().__init__("stocks", tag_date, username)
        self.name = f"securities-stocks"

    def __download_nasdaq(self) -> pd.DataFrame:
        """
        Returns a DataFrame of NASDAQ stocks
        """
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"
        response = requests.get(url, headers=nasdaq_headers())
        json_data = response.json()
        df = pd.DataFrame(data=json_data["data"]["rows"])
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
        dataset = load_dataset("edarchimbaud/securities-sp500")
        df = dataset["train"].to_pandas()
        df = df[["symbol", "security", "gics_sector", "gics_sub_industry"]]
        return df

    def __download(self) -> pd.DataFrame:
        self.dataset_df = pd.concat(
            [
                self.__download_nasdaq(),
                self.__download_sp500(),
            ]
        )
        self.dataset_df = self.dataset_df.drop_duplicates(
            subset=["symbol"], keep="first"
        )
        self.dataset_df.sort_values(by=["symbol"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)

    def set_dataset_df(self):
        """
        Frames to dataset.
        """
        self.__download()
