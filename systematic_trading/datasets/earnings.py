"""
Earnings data.
"""
from dataset import Dataset
import pandas as pd


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
