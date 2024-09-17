from datetime import date
import os
import pickle

from systematic_trading.datasets import Dataset


class Raw(Dataset):
    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.cache_dir = os.getenv("CACHE_DIR", "/tmp")
        self.frames = {}

    def append_frame(self, symbol: str):
        """
        Append frame.
        """
        raise NotImplementedError

    def get_cache_path(self):
        """
        Get cache path.
        """
        tag = self.tag_date.isoformat()
        return os.path.join(
            self.cache_dir,
            self.username,
            self.name,
            f"{tag}.pkl",
        )

    def load_frames(self):
        file_path = self.get_cache_path()
        if os.path.exists(file_path):
            with open(file_path, "rb") as file:
                self.frames = pickle.load(file)

    def save_frames(self):
        file_path = self.get_cache_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as file:
            pickle.dump(self.frames, file)
