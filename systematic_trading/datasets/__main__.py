from datetime import date, datetime
from typing import List

import click
from tqdm import tqdm

from systematic_trading.datasets.dataset import Dataset
from systematic_trading.datasets.features.features_monthly import FeaturesMonthly
from systematic_trading.datasets.index_constituents import IndexConstituents
from systematic_trading.datasets.index_constituents.sp500 import SP500
from systematic_trading.datasets.raw.analysis.earnings_estimate import EarningsEstimate
from systematic_trading.datasets.raw.analysis.eps_revisions import EPSRevisions
from systematic_trading.datasets.raw.analysis.eps_trend import EPSTrend
from systematic_trading.datasets.raw.analysis.revenue_estimate import RevenueEstimate
from systematic_trading.datasets.raw.earnings import Earnings
from systematic_trading.datasets.raw.earnings_forecast import EarningsForecast
from systematic_trading.datasets.raw.earnings_surprise import EarningsSurprise
from systematic_trading.datasets.raw.extended_trading import ExtendedTrading
from systematic_trading.datasets.raw.news import News
from systematic_trading.datasets.raw.short_interest import ShortInterest
from systematic_trading.datasets.raw.timeseries_daily import TimeseriesDaily
from systematic_trading.datasets.raw.timeseries_1mn import Timeseries1mn
from systematic_trading.datasets.targets.targets_monthly import TargetsMonthly


@click.command()
@click.option("--suffix", default="sp500", help="Suffix to use")
@click.option("--tag", default=date.today().isoformat(), help="Tag to use")
@click.option("--username", default="edarchimbaud", help="Username to use")
def main(suffix: str, tag: str, username: str):
    """
    Main function.
    """
    tag_date = datetime.strptime(tag, "%Y-%m-%d").date()
    print("Updating index constituents...")
    if suffix == "sp500":
        index_constituents = SP500(tag_date=tag_date, username=username)
    else:
        raise ValueError(f"Unknown suffix {suffix}")
    if not index_constituents.check_file_exists(tag=tag):
        index_constituents.set_dataset_df()
        index_constituents.to_hf_datasets()
    print("Updating raw datasets...")
    raw_datasets = {
        "earnings-sp500": Earnings(suffix=suffix, tag_date=tag_date, username=username),
        "earnings-estimate-sp500": EarningsEstimate(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "earnings-forecast-sp500": EarningsForecast(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "earnings-surprise-sp500": EarningsSurprise(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "extended-trading-sp500": ExtendedTrading(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "eps-revisions-sp500": EPSRevisions(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "eps-trend-sp500": EPSTrend(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "news-sp500": News(suffix=suffix, tag_date=tag_date, username=username),
        "revenue-estimate-sp500": RevenueEstimate(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "short-interest-sp500": ShortInterest(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "timeseries-daily-sp500": TimeseriesDaily(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "timeseries-1mn-sp500": Timeseries1mn(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    dataset_names = [
        name
        for name in raw_datasets
        if not raw_datasets[name].check_file_exists(tag=tag)
    ]
    for name in dataset_names:
        raw_datasets[name].load_frames()
    for symbol in tqdm(index_constituents.symbols):
        for name in dataset_names:
            if symbol in raw_datasets[name].frames:
                continue
            raw_datasets[name].append_frame(symbol)
            raw_datasets[name].save_frames()
    for name in dataset_names:
        raw_datasets[name].set_dataset_df()
        raw_datasets[name].to_hf_datasets()
    print("Updating feature and target datasets...")
    feature_target_datasets = {
        "features-monthly-sp500": FeaturesMonthly(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "targets-monthly-sp500": TargetsMonthly(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    for name in feature_target_datasets:
        feature_target_datasets[name].set_dataset_df()
        feature_target_datasets[name].to_hf_datasets()


if __name__ == "__main__":
    main()
