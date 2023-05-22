"""
EPS revision data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class EPSRevisions(Dataset):
    """
    EPS revision data.
    """

    def __init__(self):
        super().__init__()
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
        self.data = pd.DataFrame(columns=self.expected_columns)
