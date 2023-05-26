"""
Index constituents data.
"""
from datetime import date

import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class IndexConstituents(Dataset):
    """
    Index constituents data.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.expected_columns = [
            "symbol",
            "security",
            "gics_sector",
            "gics_sub_industry",
            "headquarters_location",
            "date_added",
            "cik",
            "founded",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)
