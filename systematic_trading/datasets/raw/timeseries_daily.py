"""
Timeseries daily data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class TimeseriesDaily(Dataset):
    """
    Timeseries daily data.
    """

    def __init__(self):
        super().__init__()
        self.expected_columns = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
        ]
        self.data = pd.DataFrame(columns=self.expected_columns)
