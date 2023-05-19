from datetime import date
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
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        self.name: str = None
        self.today = date.today()
        self.username: str = "edarchimbaud"
        self.sleep_time: int = 3
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

    def crawl(self) -> None:
        """
        Crawl data.
        """
        print(f"Crawl dataset: {self.name}")
        tag = self.today.isoformat()
        if self.name is None:
            raise ValueError("self.name must be set")
        if self.check_file_exists(tag=tag):
            raise ValueError("tag reference exists")
        self.download()
        self.to_hf_datasets(tag)

    def download(self) -> None:
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
            raise ValueError("self.data must have the right columns")
        if len(self.data) == 0:
            raise ValueError("self.data must be set")
        dataset = HFDataset.from_pandas(self.data)
        repo_id: str = f"edarchimbaud/{self.name}"
        dataset.push_to_hub(repo_id, private=False)
        huggingface_hub.create_tag(repo_id, tag=tag, repo_type="dataset")
