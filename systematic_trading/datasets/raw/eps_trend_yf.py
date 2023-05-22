"""
EPS Trend from Yahoo Finance.
"""
import datetime
from typing import Union

from datasets import load_dataset
import pandas as pd
import time
from tqdm import tqdm

from systematic_trading.datasets.raw.analysis_yf import AnalysisYF
from systematic_trading.datasets.raw.eps_trend import EPSTrend


class EPSTrendYF(AnalysisYF, EPSTrend):
    """
    EPS Trend from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"eps-trend-{self.suffix}"
        self._exception_whitelist = ["L", "MTB", "NWS"]

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

    def download(self):
        """
        Download the EPS trend data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            try:
                data = self.get_analysis(ticker)
                df = self.data_to_df(
                    data=data[3]["EPS Trend"],
                    field="EPS Trend",
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
        # if self.check_file_exists():
        #     self.add_previous_data()
        self.data.sort_values(by=["symbol", "date"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    eps_trend_yf = EPSTrendYF()
    eps_trend_yf.crawl()


if __name__ == "__main__":
    main()
