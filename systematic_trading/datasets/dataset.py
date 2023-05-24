from datetime import date, timedelta
import time
from typing import Optional

from datasets import Dataset as HFDataset, load_dataset
import huggingface_hub
import pandas as pd
import re


class Dataset:
    """
    Dataset.
    """

    def __init__(self):
        self.expected_columns = []
        self.data: pd.DataFrame = pd.DataFrame(columns=self.expected_columns)
        self.name: str = None
        self.tag_date = date.today() - timedelta(days=1)
        self.username: str = "edarchimbaud"
        self.sleep_time: int = 10
        self.suffix: str = "sp500"

    def add_previous_data(self):
        """
        Add previous data to the current data.
        """
        symbols = self.get_index_symbols()
        prev_data = pd.DataFrame(
            load_dataset(f"{self.username}/{self.name}")["train"],
        )
        # filter out news that are not related to the index
        still_in_index = prev_data.symbol.isin(symbols)
        prev_data = prev_data.loc[still_in_index]
        self.data = pd.concat([prev_data, self.data])
        self.data.drop_duplicates(inplace=True)

    def check_file_exists(self, tag: Optional[str] = None) -> bool:
        """
        Check if file exists.
        """
        try:
            load_dataset(f"{self.username}/{self.name}", revision=tag)
            return True
        except FileNotFoundError:
            return False

    def update(self) -> None:
        """
        Crawl data.
        """
        print(f"Crawl dataset: {self.name}")
        tag = self.tag_date.isoformat()
        if self.name is None:
            raise ValueError("self.name must be set")
        if self.check_file_exists(tag=tag):
            raise ValueError("tag reference exists")
        self.build()
        self.to_hf_datasets(tag)

    def build(self) -> None:
        """
        Download data.
        """
        raise NotImplementedError

    def get_index_symbols(self):
        return load_dataset(f"{self.username}/index-constituents-{self.suffix}")[
            "train"
        ]["symbol"]

    def symbol_to_ticker(self, symbol: str) -> str:
        """
        Convert a symbol to a ticker.
        """
        pattern = re.compile(r"\.B$")
        return pattern.sub("-B", symbol)

    def to_hf_datasets(self, tag: str) -> None:
        """
        To Hugging Face datasets.
        """
        if self.data.columns.tolist() != self.expected_columns:
            raise ValueError(
                f"self.data must have the right columns\n{self.data.columns.tolist()}\n!=\n{self.expected_columns}"
            )
        if len(self.data) == 0:
            raise ValueError("self.data must be set")
        dataset = HFDataset.from_pandas(self.data)
        repo_id: str = f"edarchimbaud/{self.name}"
        dataset.push_to_hub(repo_id, private=False)
        huggingface_hub.create_tag(repo_id, tag=tag, repo_type="dataset")
