"""
News data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class News(Dataset):
    """
    News data.
    """

    def __init__(self):
        super().__init__()
        self.expected_columns = [
            "symbol",
            "body",
            "publisher",
            "publish_time",
            "title",
            "url",
            "uuid",
        ]
        self.data = pd.DataFrame(columns=self.expected_columns)
