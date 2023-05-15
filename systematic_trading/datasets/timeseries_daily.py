"""
Daily S&P 500 data.
"""
from dataset import Dataset
import pandas as pd


class TimeseriesDaily(Dataset):
    def __init__(self):
        super().__init__()
        self._columns = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "dividends",
            "stock_splits",
        ]
        self.data = pd.DataFrame(columns=self._columns)
        self.name = None


def main():
    """
    Main function.
    """
    daily_sp500 = DailySP500()
    daily_sp500.download()


if __name__ == "__main__":
    main()
