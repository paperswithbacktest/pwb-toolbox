from datetime import date, timedelta
from typing import Optional

from datasets import Dataset as HFDataset, load_dataset
import huggingface_hub
import pandas as pd
import re


class Dataset:
    """
    Dataset.
    """

    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        self.suffix: str = suffix
        self.tag_date = tag_date
        self.username: str = username
        self.expected_columns = []
        self.dataset_df: pd.DataFrame = pd.DataFrame(columns=self.expected_columns)
        self.name: str = None
        self.symbols = self.get_index_symbols()

    def add_previous_data(self):
        """
        Add previous data to the current data.
        """
        prev_data = pd.DataFrame(
            load_dataset(f"{self.username}/{self.name}")["train"],
        )
        # filter out news that are not related to the index
        still_in_index = prev_data.symbol.isin(self.symbols)
        prev_data = prev_data.loc[still_in_index]
        self.dataset_df = pd.concat([prev_data, self.dataset_df])
        self.dataset_df.drop_duplicates(inplace=True)

    def check_file_exists(self, tag: Optional[str] = None) -> bool:
        """
        Check if file exists.
        """
        try:
            load_dataset(
                f"{self.username}/{self.name}",
                revision=tag,
                verification_mode="no_checks",
            )
            return True
        except FileNotFoundError:
            return False

    def set_dataset_df(self):
        """
        Frames to dataset.
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

    def to_hf_datasets(self) -> None:
        """
        To Hugging Face datasets.
        """
        if self.dataset_df.columns.tolist() != self.expected_columns:
            raise ValueError(
                f"self.dataset_df must have the right columns\n{self.dataset_df.columns.tolist()}\n!=\n{self.expected_columns}"
            )
        if len(self.dataset_df) == 0:
            raise ValueError("self.dataset_df must be set")
        tag = self.tag_date.isoformat()
        dataset = HFDataset.from_pandas(self.dataset_df)
        repo_id: str = f"edarchimbaud/{self.name}"
        dataset.push_to_hub(repo_id, private=False)
        huggingface_hub.create_tag(repo_id, tag=tag, repo_type="dataset")
