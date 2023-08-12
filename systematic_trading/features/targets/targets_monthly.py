from datetime import date

from datasets import load_dataset
import numpy as np
import pandas as pd

from systematic_trading.datasets import Dataset


class TargetsMonthly(Dataset):
    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"targets-monthly-{self.suffix}"
        self.expected_columns = ["symbol", "date", "return", "return_quintile"]

    def __return_to_quintile(self, returns_arr):
        # I am allowed to use the future to calculate the percentiles
        percentiles = np.percentile(returns_arr, [20, 40, 60, 80])
        quintile_id = []
        for ret in returns_arr:
            if ret <= percentiles[0]:
                quintile_id.append(-2)
            elif ret <= percentiles[1]:
                quintile_id.append(-1)
            elif ret <= percentiles[2]:
                quintile_id.append(0)
            elif ret <= percentiles[3]:
                quintile_id.append(1)
            else:
                quintile_id.append(2)
        return quintile_id

    def set_dataset_df(self):
        """
        Compute the dataset.
        """
        timeseries_daily_df = pd.DataFrame(
            load_dataset(
                f"{self.username}/timeseries-daily-{self.suffix}",
                revision=self.tag_date.isoformat(),
                split="train",
            ),
        )
        timeseries_daily_df["date"] = pd.to_datetime(timeseries_daily_df["date"])
        timeseries_daily_df.set_index("date", inplace=True)
        # Cross-sectional returns
        monthly_df = (
            timeseries_daily_df.groupby("symbol")["close"]
            .resample("M")
            .last()
            .pct_change()
            .shift(-1)
        )
        monthly_df = monthly_df.reset_index(level=["symbol", "date"]).dropna()
        monthly_df.rename(columns={"close": "return"}, inplace=True)
        monthly_df["return_quintile"] = monthly_df.groupby("date")["return"].transform(
            lambda x: pd.qcut(x, 5, labels=False)
        )
        monthly_df.reset_index(drop=True, inplace=True)
        self.dataset_df = monthly_df
