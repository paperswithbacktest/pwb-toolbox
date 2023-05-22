"""
Earnings data.
"""
import pandas as pd

from systematic_trading.datasets.dataset import Dataset


class Earnings(Dataset):
    """
    Earnings data.
    """

    def __init__(self):
        super().__init__()
        self.expected_columns = [
            "symbol",
            "date",
            "eps_estimate",
            "reported_eps",
            "surprise",
        ]
        self.data = pd.DataFrame(columns=self.expected_columns)
