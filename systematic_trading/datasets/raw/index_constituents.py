"""
Index constituents data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class IndexConstituents(Dataset):
    """
    Index constituents data.
    """

    def __init__(self):
        super().__init__()
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
        self.data = pd.DataFrame(columns=self.expected_columns)
