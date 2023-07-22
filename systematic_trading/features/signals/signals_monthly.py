from datetime import date
import os

from datasets import load_dataset
from numba import jit
import numpy as np
import pandas as pd
import pickle
from tqdm import tqdm

from systematic_trading.datasets.dataset import Dataset
from systematic_trading.features.signals.estimators.slope import (
    bayesian_slope,
    linear_regression_slope,
    median_of_local_slopes,
    median_of_progressive_slopes,
    barycentre_of_progressive_slopes,
)


class SignalsMonthly(Dataset):
    def __init__(self, suffix: str = None, tag_date: date = None, username: str = None):
        super().__init__(suffix, tag_date, username)
        self.name = f"signals-monthly-{self.suffix}"
        self.expected_columns = [
            "symbol",
            "date",
            "bayesian_slope_12m",
            "linear_regression_slope_12m",
            "median_of_progressive_slopes_12m",
            "median_of_local_slopes_12m",
            "barycentre_of_progressive_slopes_12m",
            "bayesian_slope_12m_quintile",
            "linear_regression_slope_12m_quintile",
            "median_of_progressive_slopes_12m_quintile",
            "median_of_local_slopes_12m_quintile",
            "barycentre_of_progressive_slopes_12m_quintile",
        ]

    def set_dataset_df(self):
        path = os.path.join(os.getenv("HOME"), "Downloads", "timeseries_daily_df.pkl")
        if os.path.exists(path):
            with open(path, "rb") as handler:
                timeseries_daily_df = pickle.load(handler)
        else:
            timeseries_daily_df = pd.DataFrame(
                load_dataset(
                    f"{self.username}/timeseries-daily-{self.suffix}",
                    revision=self.tag_date.isoformat(),
                    split="train",
                ),
            )
            with open(path, "wb") as handler:
                pickle.dump(timeseries_daily_df, handler)
        timeseries_daily_df["date"] = pd.to_datetime(timeseries_daily_df["date"])
        timeseries_daily_df.set_index("date", inplace=True)
        BARYCENTRE_OF_PROGRESSIVE_SLOPES_12M = "barycentre_of_progressive_slopes_12m"
        signals = {
            "bayesian_slope_12m": bayesian_slope,
            "linear_regression_slope_12m": linear_regression_slope,
            "median_of_progressive_slopes_12m": median_of_progressive_slopes,
            "median_of_local_slopes_12m": median_of_local_slopes,
            BARYCENTRE_OF_PROGRESSIVE_SLOPES_12M: "custom",
        }
        frames = []
        for signal_name, signal in tqdm(signals.items()):
            if signal != "custom":
                monthly_df = (
                    timeseries_daily_df.groupby("symbol")["close"]
                    .resample("M")
                    .last()
                    .rolling(window=12)
                    .apply(signal)
                )
                monthly_df.rename(signal_name, inplace=True)
            elif signal_name == BARYCENTRE_OF_PROGRESSIVE_SLOPES_12M:
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
                )[["close"]]
                monthly_df.rename(
                    columns={"close": BARYCENTRE_OF_PROGRESSIVE_SLOPES_12M},
                    inplace=True,
                )
            frames.append(monthly_df)
        monthly_df = pd.concat(frames, axis=1)
        monthly_df = monthly_df.reset_index(level=["symbol", "date"]).dropna()
        for signal_name in signals.keys():
            monthly_df[f"{signal_name}_quintile"] = monthly_df.groupby("date")[
                signal_name
            ].transform(lambda x: pd.qcut(x, 5, labels=False))
        monthly_df.reset_index(drop=True, inplace=True)
        self.dataset_df = monthly_df
