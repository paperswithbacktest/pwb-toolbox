from datetime import date

from datasets import Dataset as HFDataset
import huggingface_hub
import pandas as pd


class Dataset:
    """
    Dataset.
    """

    def __init__(self):
        self._columns = []
        self.data = pd.DataFrame(columns=self._columns)
        self.name = None

    def download(self):
        """
        Download data.
        """
        raise NotImplementedError

    def to_hf_datasets(self):
        """
        To Hugging Face datasets.
        """
        if self.name is None:
            raise ValueError("self.name must be set")
        if self.data.columns.tolist() != self._columns:
            raise ValueError("self.data must have the right columns")
        if len(self.data) == 0:
            raise ValueError("self.data must be set")
        dataset = HFDataset.from_pandas(self.data)
        repo_id = f"edarchimbaud/{self.name}"
        dataset.push_to_hub(repo_id, private=False)
        huggingface_hub.create_tag(
            repo_id, tag=date.today().isoformat(), repo_type="dataset"
        )
