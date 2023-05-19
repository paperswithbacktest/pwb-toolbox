"""
Index constituents S&P 500.
"""
from bs4 import BeautifulSoup
import pandas as pd
import requests
from tqdm import tqdm

from index_constituents import IndexConstituents


class IndexConstituentsSP500(IndexConstituents):
    """
    Index constituents S&P 500.
    """

    def __init__(self):
        super().__init__()
        self.name = f"index-constituents-{self.suffix}"

    def download(self):
        """
        Download the list of S&P 500 constituents from Wikipedia.
        """
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = requests.get(url, headers=self.headers)
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
                    "headquarters_location": td_tags[
                        header.index("Headquarters Location")
                    ].text.strip(),
                    "date_added": td_tags[header.index("Date added")].text.strip(),
                    "cik": td_tags[header.index("CIK")].text.strip(),
                    "founded": td_tags[header.index("Founded")].text.strip(),
                }
            )
        self.data = pd.DataFrame(data=data)
        self.data.sort_values(by=["symbol"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    index_constituents_sp500 = IndexConstituentsSP500()
    index_constituents_sp500.crawl()


if __name__ == "__main__":
    main()
