from datasets import load_dataset
import pandas as pd

from dataset import Dataset


class Features(Dataset):
    def __init__(self):
        pass

    def compute(self):
        dataset = load_dataset(
            f"{self.username}/news-{self.suffix}",
            revision="2023-05-15",
            split="train",
        )
        df = pd.DataFrame(dataset)
        print(df)


def main():
    features = Features()
    features.compute()


if __name__ == "__main__":
    main()
