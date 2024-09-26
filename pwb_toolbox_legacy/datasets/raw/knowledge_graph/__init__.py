"""
Index constituents data.
"""
from datetime import date

import pandas as pd

from pwb_toolbox.datasets import Dataset


class KnowledgeGraph(Dataset):
    """
    Index constituents data.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.expected_columns = [
            "symbol",
            "security",
            "country",
            "gics_sector",
            "gics_sub_industry",
            "categories",
        ]
        self.dataset_df = pd.DataFrame(columns=self.expected_columns)
