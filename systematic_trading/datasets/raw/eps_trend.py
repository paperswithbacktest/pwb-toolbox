"""
EPS trend data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class EPSTrend(Dataset):
    """
    EPS trend data.
    """

    def __init__(self):
        super().__init__()
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
        self.data = pd.DataFrame(columns=self.expected_columns)
