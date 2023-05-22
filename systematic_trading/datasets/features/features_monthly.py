import os

from datasets import load_dataset
from numba import jit
import numpy as np
import pandas as pd
import pickle

from systematic_trading.datasets.dataset import Dataset
from systematic_trading.datasets.features.estimators.slope import (
    bayesian_slope,
    linear_regression_slope,
    median_of_local_slopes,
    median_of_progressive_slopes,
    barycentre_of_progressive_slopes,
)


class FeaturesMonthly(Dataset):
    def __init__(self):
        super().__init__()
        self.name = f"features-monthly-{self.suffix}"
        self.expected_columns = ["symbol", "date", "return_12m"]

    def compute(self):
        path = os.path.join(os.getenv("HOME"), "Downloads", "timeseries_daily_df.pkl")
        if os.path.exists(path):
            with open(path, "rb") as handler:
                timeseries_daily_df = pickle.load(handler)
        else:
            timeseries_daily_df = pd.DataFrame(
                load_dataset(
                    f"{self.username}/timeseries-daily-{self.suffix}",
                    revision=self.today.isoformat(),
                    split="train",
                ),
            )
            with open(path, "wb") as handler:
                pickle.dump(timeseries_daily_df, handler)
        timeseries_daily_df["date"] = pd.to_datetime(timeseries_daily_df["date"])
        timeseries_daily_df.set_index("date", inplace=True)
        # Bayesian slope
        monthly_df = (
            timeseries_daily_df.groupby("symbol")["close"]
            .resample("M")
            .last()
            .rolling(window=12)
            .apply(bayesian_slope)
        )
        print("Bayesian slope", monthly_df)
        # monthly_df = monthly_df.reset_index(level=["symbol", "date"]).dropna()
        # monthly_df.rename(columns={"close": "return_12m"}, inplace=True)
        # monthly_df["return_12m_quintile"] = monthly_df.groupby("date")[
        #     "return_12m"
        # ].transform(lambda x: pd.qcut(x, 5, labels=False))
        # Slope of the linear regression
        monthly_df = (
            timeseries_daily_df.groupby("symbol")["close"]
            .resample("M")
            .last()
            .rolling(window=12)
            .apply(linear_regression_slope)
        )
        print("Linear regression slope", monthly_df)
        # Median of the progressive slopes
        monthly_df = (
            timeseries_daily_df.groupby("symbol")["close"]
            .resample("M")
            .last()
            .rolling(window=12)
            .apply(median_of_progressive_slopes)
        )
        print("Median of progressive slopes", monthly_df)
        # Median of local slopes
        monthly_df = (
            timeseries_daily_df.groupby("symbol")["close"]
            .resample("M")
            .last()
            .rolling(window=12)
            .apply(median_of_local_slopes)
        )
        print("Median of local slopes", monthly_df)
        # Barycentre of progressive slopes
        monthly_close_df = (
            timeseries_daily_df.groupby("symbol")["close"].resample("M").last()
        )
        monthly_volume_df = (
            timeseries_daily_df.groupby("symbol")["volume"].resample("M").sum()
        )
        monthly_df = pd.concat([monthly_close_df, monthly_volume_df], axis=1)
        monthly_df = monthly_df.rolling(window=12, method="table").apply(
            barycentre_of_progressive_slopes,
            raw=True,
            engine="numba",
        )
        print("Barycentre of progressive slopes", monthly_df)

        # monthly_df.reset_index(drop=True, inplace=True)
        # self.data = monthly_df


def main():
    features_monthly = FeaturesMonthly()
    features_monthly.today = pd.to_datetime("2023-05-19").date()
    features_monthly.compute()
    # features_monthly.to_hf_datasets(tag=features_monthly.today.isoformat())


if __name__ == "__main__":
    main()
