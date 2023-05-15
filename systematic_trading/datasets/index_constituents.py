from dataset import Dataset
import pandas as pd


class IndexConstituents(Dataset):
    def __init__(self):
        super().__init__()
        self._columns = [
            "symbol",
            "security",
            "gics_sector",
            "gics_sub_industry",
            "headquarters_location",
            "date_added",
            "cik",
            "founded",
        ]
        self.data = pd.DataFrame(columns=self._columns)
        self.name = None
