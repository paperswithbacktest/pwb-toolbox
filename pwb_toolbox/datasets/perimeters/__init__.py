"""
Index constituents data.
"""
from datetime import date

import pandas as pd

from systematic_trading.datasets import Dataset


class Perimeter(Dataset):
    """
    Perimeter data.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.expected_columns = [
            "symbol",
            "security",
            "gics_sector",
            "gics_sub_industry",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)
