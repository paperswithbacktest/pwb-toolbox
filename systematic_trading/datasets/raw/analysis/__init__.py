"""
Earnings data.
"""
from typing import Union

from bs4 import BeautifulSoup
import pandas as pd
import re
import requests

from systematic_trading.datasets.raw import Raw
from systematic_trading.helpers import retry_get


class Analysis(Raw):
    """
    Analysis data from Yahoo Finance.
    """

    def get_analysis(self, ticker: str) -> pd.DataFrame:
        """
        Get analysis for a given ticker.
        """
        url = f"https://finance.yahoo.com/quote/{ticker}/analysis?p={ticker}"
        response = retry_get(url)
        soup = BeautifulSoup(response.text, features="lxml")
        div = soup.find("div", {"id": "Col1-0-AnalystLeafPage-Proxy"})
        tables = div.find_all("table") if div is not None else None
        if tables is None:
            raise ValueError(f"No tables found for {ticker}")
        expected_table_names = [
            "Earnings Estimate",
            "Revenue Estimate",
            "Earnings History",
            "EPS Trend",
            "EPS Revisions",
            "Growth Estimates",
        ]
        data = []
        for index, expected_table_name in enumerate(expected_table_names):
            table = tables[index]
            thead = table.find("thead")
            header = [th.text for th in thead.find_all("th")]
            assert len(header) == 5
            assert header[0] == expected_table_name
            tbody = table.find("tbody")
            table_data = []
            for row in tbody.find_all("tr"):
                table_data.append(
                    {k: row.find_all("td")[i].text for i, k in enumerate(header)}
                )
            data.append(
                {
                    expected_table_name: table_data,
                }
            )
        assert len(data) > 0
        return data

    def __format_column(self, column: str) -> str:
        """
        Format column.
        """
        return re.sub(r"[^a-z0-9_]", "", column.replace(" ", "_").lower())

    def format_value(self, column: str, value: str) -> Union[float, None]:
        raise NotImplementedError

    def data_to_df(
        self,
        data,
        field: str,
        symbol: str,
    ) -> pd.DataFrame:
        df = pd.DataFrame(data=data)
        df.set_index(field, inplace=True, drop=True)
        data_dict = {}
        for index, row in df.iterrows():
            for col in df.columns:
                period_column = self.__format_column(col.split(" (")[0])
                period = col.split(" (")[1].replace(")", "")
                data_dict[period_column] = self.format_value(period_column, period)
                column = self.__format_column(index + " " + period_column)
                data_dict[column] = self.format_value(column, row[col])
        df = pd.DataFrame(data=[data_dict])
        df["date"] = self.tag_date.isoformat()
        df["symbol"] = symbol
        df = df.reindex(columns=["symbol", "date"] + list(df.columns[:-2]))
        return df
