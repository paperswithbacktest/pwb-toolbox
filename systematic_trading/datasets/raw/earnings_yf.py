"""
Earnings data from Yahoo Finance.
"""
from datetime import datetime
from typing import Union

from bs4 import BeautifulSoup
from datasets import load_dataset
import pandas as pd
import pytz
import requests
import time
from tqdm import tqdm

from systematic_trading.datasets.raw.earnings import Earnings
from systematic_trading.helpers import retry_get


class EarningsYF(Earnings):
    """
    Earnings data from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"earnings-{self.suffix}"
        self._exception_whitelist = ["FOX", "NWS"]

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

    def download(self):
        """
        Download the quarterly earnings data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            try:
                df = self.__get_earnings(ticker)
            except ValueError as e:
                if symbol in self._exception_whitelist:
                    print(f"Exception for {symbol}: {e}")
                    continue
                else:
                    raise e
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
            frames.append(df)
            time.sleep(self.sleep_time)
        self.data = pd.concat(frames)
        self.data.sort_values(by=["symbol", "date"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    earnings_yf = EarningsYF()
    earnings_yf.crawl()


if __name__ == "__main__":
    main()
