"""
Earnings data from Yahoo Finance.
"""
from datetime import datetime, date
from typing import Union

from bs4 import BeautifulSoup
from datasets import load_dataset
import pandas as pd
import pytz
import requests

from systematic_trading.datasets.raw import Raw
from systematic_trading.helpers import retry_get


class Earnings(Raw):
    """
    Earnings data from Yahoo Finance.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"earnings-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "eps_estimate",
            "reported_eps",
            "surprise",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def __format_field(self, key: str, value: str):
        """
        Format a field.
        """
        if key == "Earnings Date":
            date_str = value[:-3]
            datetime_obj = datetime.strptime(date_str, "%b %d, %Y, %I %p")
            tz_str = value[-3:]
            if tz_str in ["EST", "EDT"]:
                tz = pytz.timezone("EST")
            else:
                raise ValueError(f"Unknown timezone: {tz_str}")
            return tz.localize(datetime_obj)
        elif key in ["EPS Estimate", "Reported EPS", "Surprise(%)"]:
            if value == "-":
                return None
            return float(value)
        elif key in ["Symbol", "Company"]:
            return value
        else:
            raise ValueError(f"Unknown key: {key}")

    def __get_earnings(self, ticker: str) -> Union[pd.DataFrame, None]:
        """
        Get earnings for a given ticker.
        """
        url = f"https://finance.yahoo.com/calendar/earnings?symbol={ticker}"
        response = retry_get(url)
        soup = BeautifulSoup(response.text, features="lxml")
        div = soup.find("div", {"id": "cal-res-table"})
        if div is None:
            raise ValueError(f"Could not find earnings for {ticker}")
        table = div.find("table")
        thead = table.find("thead")
        header = [th.text for th in thead.find_all("th")]
        expected_header = [
            "Symbol",
            "Company",
            "Earnings Date",
            "EPS Estimate",
            "Reported EPS",
            "Surprise(%)",
        ]
        assert header == expected_header
        tbody = table.find("tbody")
        data = []
        for row in tbody.find_all("tr"):
            data.append(
                {
                    key: self.__format_field(
                        key,
                        value=row.find_all("td")[index].text,
                    )
                    for index, key in enumerate(header)
                }
            )
        assert len(data) > 0
        df = pd.DataFrame(data)
        return df

    def append_frame(self, symbol: str):
        """
        Append a dataframe for a given symbol.
        """
        ticker = self.symbol_to_ticker(symbol)
        try:
            df = self.__get_earnings(ticker)
        except ValueError as e:
            print(f"Exception for {self.name}: {symbol}: {e}")
            return
        df.drop(columns=["Symbol", "Company"], inplace=True)
        df.rename(
            columns={
                "Earnings Date": "date",
                "EPS Estimate": "eps_estimate",
                "Reported EPS": "reported_eps",
                "Surprise(%)": "surprise",
            },
            inplace=True,
        )
        df["symbol"] = symbol
        # use reindex() to set 'symbol' as the first column
        df = df.reindex(columns=["symbol"] + list(df.columns[:-1]))
        self.frames[symbol] = df

    def set_dataset_df(self):
        """
        Set the dataset dataframe.
        """
        self.dataset_df = pd.concat(self.frames.values())
        self.dataset_df.sort_values(by=["symbol", "date"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)
