"""
EPS Revisions from Yahoo Finance.
"""
from datetime import date
from typing import Union

from datasets import load_dataset
import pandas as pd

from systematic_trading.datasets.raw.analysis import Analysis


class EPSRevisions(Analysis):
    """
    EPS Revisions from Yahoo Finance.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"eps-revisions-{suffix}"
        self._exception_whitelist = ["L", "MTB", "NWS"]
        self.expected_columns = [
            "symbol",
            "date",
            "current_qtr",
            "up_last_7_days_current_qtr",
            "next_qtr",
            "up_last_7_days_next_qtr",
            "current_year",
            "up_last_7_days_current_year",
            "next_year",
            "up_last_7_days_next_year",
            "up_last_30_days_current_qtr",
            "up_last_30_days_next_qtr",
            "up_last_30_days_current_year",
            "up_last_30_days_next_year",
            "down_last_7_days_current_qtr",
            "down_last_7_days_next_qtr",
            "down_last_7_days_current_year",
            "down_last_7_days_next_year",
            "down_last_30_days_current_qtr",
            "down_last_30_days_next_qtr",
            "down_last_30_days_current_year",
            "down_last_30_days_next_year",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def format_value(self, key: str, value: str) -> Union[int, float]:
        """
        Format value.
        """
        if value == "N/A":
            return None
        elif "_last_" in key:
            return int(value)
        elif key == "current_qtr" or key == "next_qtr":
            return value
        elif key == "current_year" or key == "next_year":
            return int(value)
        else:
            raise ValueError(f"Unknown key: {key}")

    def append_frame(self, symbol: str) -> None:
        ticker = self.symbol_to_ticker(symbol)
        try:
            data = self.get_analysis(ticker)
            df = self.data_to_df(
                data=data[4]["EPS Revisions"],
                field="EPS Revisions",
                symbol=symbol,
            )
        except IndexError as e:
            if symbol in self._exception_whitelist:
                print(f"Exception for {symbol}: {e}")
                return
            else:
                raise e
        self.frames[symbol] = df

    def set_dataset_df(self):
        self.dataset_df = pd.concat(self.frames.values())
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "date"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)
