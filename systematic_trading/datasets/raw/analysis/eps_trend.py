"""
EPS Trend from Yahoo Finance.
"""
from datetime import date
from typing import Union

from datasets import load_dataset
import pandas as pd

from systematic_trading.datasets.raw.analysis import Analysis


class EPSTrend(Analysis):
    """
    EPS Trend from Yahoo Finance.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"eps-trend-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "current_qtr",
            "current_estimate_current_qtr",
            "next_qtr",
            "current_estimate_next_qtr",
            "current_year",
            "current_estimate_current_year",
            "next_year",
            "current_estimate_next_year",
            "7_days_ago_current_qtr",
            "7_days_ago_next_qtr",
            "7_days_ago_current_year",
            "7_days_ago_next_year",
            "30_days_ago_current_qtr",
            "30_days_ago_next_qtr",
            "30_days_ago_current_year",
            "30_days_ago_next_year",
            "60_days_ago_current_qtr",
            "60_days_ago_next_qtr",
            "60_days_ago_current_year",
            "60_days_ago_next_year",
            "90_days_ago_current_qtr",
            "90_days_ago_next_qtr",
            "90_days_ago_current_year",
            "90_days_ago_next_year",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def format_value(self, key: str, value: str) -> Union[int, float]:
        """
        Format value.
        """
        if value == "N/A":
            return None
        elif key.startswith("current_estimate") or "_days_ago_" in key:
            return float(value)
        elif key == "current_qtr" or key == "next_qtr":
            return value
        elif key == "current_year" or key == "next_year":
            return int(value)
        else:
            raise ValueError(f"Unknown key: {key}")

    def append_frame(self, symbol: str):
        ticker = self.symbol_to_ticker(symbol)
        try:
            data = self.get_analysis(ticker)
            df = self.data_to_df(
                data=data[3]["EPS Trend"],
                field="EPS Trend",
                symbol=symbol,
            )
        except IndexError as e:
            print(f"Exception for {self.name}: {symbol}: {e}")
            return
        self.frames[symbol] = df

    def set_dataset_df(self):
        """
        Download the EPS trend data from Yahoo Finance.
        """
        self.dataset_df = pd.concat(self.frames.values())
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "date"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)
