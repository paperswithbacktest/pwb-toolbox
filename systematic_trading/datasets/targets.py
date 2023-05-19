from datasets import load_dataset
import pandas as pd


class Targets:
    def __init__(self):
        pass

    def compute(self):
        dataset = load_dataset(
            f"{self.username}/timeseries-daily-{self.suffix}",
            revision="2023-05-15",
            split="train",
        )
        df = pd.DataFrame(dataset)
        print(df)


def main():
    targets = Targets()
    targets.compute()
    # TODO: bien gérer le versioning cumulatif des datasets


if __name__ == "__main__":
    main()
