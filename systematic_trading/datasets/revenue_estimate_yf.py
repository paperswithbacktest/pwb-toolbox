"""
Revenue estimate from Yahoo Finance.
"""
import datetime
from typing import Union

from datasets import load_dataset
import pandas as pd
import time
from tqdm import tqdm

from analysis_yf import AnalysisYF
from revenue_estimate import RevenueEstimate


class RevenueEstimateYF(AnalysisYF, RevenueEstimate):
    """
    Revenue estimate from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"revenue-estimate-{self.suffix}"
        self._exception_whitelist = ["L", "MTB", "NWS"]

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

    def download(self):
        """
        Download the quarterly revenue data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            try:
                data = self.get_analysis(ticker)
                df = self.data_to_df(
                    data=data[1]["Revenue Estimate"],
                    field="Revenue Estimate",
                    symbol=symbol,
                )
            except IndexError as e:
                if symbol in self._exception_whitelist:
                    print(f"Exception for {symbol}: {e}")
                    continue
                else:
                    raise e
            frames.append(df)
            time.sleep(self.sleep_time)
        self.data = pd.concat(frames)
        if self.check_file_exists():
            self.add_previous_data()
        self.data.sort_values(by=["symbol", "date"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    revenue_estimate_yf = RevenueEstimateYF()
    revenue_estimate_yf.crawl()


if __name__ == "__main__":
    main()
