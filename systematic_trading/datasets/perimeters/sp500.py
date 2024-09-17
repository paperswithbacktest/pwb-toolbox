"""
Index constituents S&P 500.
"""
from datetime import date

from bs4 import BeautifulSoup
import pandas as pd
import requests
from tqdm import tqdm

from systematic_trading.datasets.perimeters import Perimeter
from systematic_trading.helpers import retry_get


class SP500(Perimeter):
    """
    Index constituents S&P 500.
    """

    def __init__(self, tag_date: date = None, username: str = None):
        super().__init__("sp500", tag_date, username)
        self.name = f"perimeter-sp500"

    def set_dataset_df(self):
        """
        Download the list of S&P 500 constituents from Wikipedia.
        """
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = retry_get(url)
        body_html = response.content.decode("utf-8")
        soup = BeautifulSoup(body_html, features="lxml")
        table = soup.find("table", {"id": "constituents"})
        header = [th.text.strip() for th in table.find_all("th")]
        assert len(header) == 8, f"len(header)=={len(header)}"
        tbody = table.find("tbody")
        data = []
        for row in tqdm(tbody.find_all("tr")):
            td_tags = row.find_all("td")
            if len(td_tags) != len(header):
                continue
            data.append(
                {
                    "symbol": td_tags[header.index("Symbol")].text.strip(),
                    "security": td_tags[header.index("Security")].text.strip(),
                    "gics_sector": td_tags[header.index("GICS Sector")].text.strip(),
                    "gics_sub_industry": td_tags[
                        header.index("GICS Sub-Industry")
                    ].text.strip(),
                    # "headquarters_location": td_tags[
                    #     header.index("Headquarters Location")
                    # ].text.strip(),
                    # "date_added": td_tags[header.index("Date added")].text.strip(),
                    # "cik": td_tags[header.index("CIK")].text.strip(),
                    # "founded": td_tags[header.index("Founded")].text.strip(),
                }
            )
        self.dataset_df = pd.DataFrame(data=data)
        self.dataset_df.sort_values(by=["symbol"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)
