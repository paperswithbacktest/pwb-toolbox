"""
Revenue estimate from Yahoo Finance.
"""
from datetime import date
from typing import Union

from datasets import load_dataset
import pandas as pd

from systematic_trading.datasets.raw.analysis import Analysis


class RevenueEstimate(Analysis):
    """
    Revenue estimate from Yahoo Finance.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"revenue-estimate-{suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "current_qtr",
            "no_of_analysts_current_qtr",
            "next_qtr",
            "no_of_analysts_next_qtr",
            "current_year",
            "no_of_analysts_current_year",
            "next_year",
            "no_of_analysts_next_year",
            "avg_estimate_current_qtr",
            "avg_estimate_next_qtr",
            "avg_estimate_current_year",
            "avg_estimate_next_year",
            "low_estimate_current_qtr",
            "low_estimate_next_qtr",
            "low_estimate_current_year",
            "low_estimate_next_year",
            "high_estimate_current_qtr",
            "high_estimate_next_qtr",
            "high_estimate_current_year",
            "high_estimate_next_year",
            "year_ago_sales_current_qtr",
            "year_ago_sales_next_qtr",
            "year_ago_sales_current_year",
            "year_ago_sales_next_year",
            "sales_growth_yearest_current_qtr",
            "sales_growth_yearest_next_qtr",
            "sales_growth_yearest_current_year",
            "sales_growth_yearest_next_year",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)

    def format_value(self, key: str, value: str) -> Union[int, float]:
        """
        Format value.
        """
        if value == "N/A":
            return None
        elif key.startswith("no_of_analysts"):
            return int(value)
        elif (
            key.startswith("avg_estimate")
            or key.startswith("low_estimate")
            or key.startswith("high_estimate")
            or key.startswith("year_ago_sales")
            or key.startswith("sales_growth_yearest")
        ):
            return value
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
                data=data[1]["Revenue Estimate"],
                field="Revenue Estimate",
                symbol=symbol,
            )
        except IndexError as e:
            print(f"Exception for {self.name}: {symbol}: {e}")
            return
        self.frames[symbol] = df

    def set_dataset_df(self):
        self.dataset_df = pd.concat(self.frames.values())
        if self.check_file_exists():
            self.add_previous_data()
        self.dataset_df.sort_values(by=["symbol", "date"], inplace=True)
        self.dataset_df.reset_index(drop=True, inplace=True)
