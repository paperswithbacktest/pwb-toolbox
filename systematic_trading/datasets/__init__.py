import concurrent.futures
from datetime import date, timedelta

import click
from systematic_trading.datasets.dataset import Dataset
from systematic_trading.datasets.features.features_monthly import FeaturesMonthly
from systematic_trading.datasets.raw.earnings_yf import EarningsYF
from systematic_trading.datasets.raw.earnings_estimate_yf import EarningsEstimateYF
from systematic_trading.datasets.raw.eps_revisions_yf import EPSRevisionsYF
from systematic_trading.datasets.raw.eps_trend_yf import EPSTrendYF
from systematic_trading.datasets.raw.index_constituents_sp500 import (
    IndexConstituentsSP500,
)
from systematic_trading.datasets.raw.news_yf import NewsYF
from systematic_trading.datasets.raw.revenue_estimate_yf import RevenueEstimateYF
from systematic_trading.datasets.raw.timeseries_daily_yf import TimeseriesDailyYF
from systematic_trading.datasets.targets.targets_monthly import TargetsMonthly


def update(dataset: Dataset, tag_date: date, username: str):
    """
    Crawl the data.
    """
    dataset.suffix = "sp500"
    dataset.tag_date = tag_date
    dataset.username = username
    try:
        dataset.update()
    except ValueError as err:
        print(err)


def update_all(username: str):
    """
    Update all datasets.

    Args:
        username (str): Username to use.
    """
    tag_date = date.today() - timedelta(days=1)

    update(IndexConstituentsSP500(), tag_date, username)

    datasets = [
        EarningsYF(),
        EarningsEstimateYF(),
        EPSRevisionsYF(),
        EPSTrendYF(),
        NewsYF(),
        RevenueEstimateYF(),
        TimeseriesDailyYF(),
    ]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(update, dataset, tag_date, username) for dataset in datasets
        ]
        concurrent.futures.wait(futures)

    if TimeseriesDailyYF().check_file_exists(tag=tag_date.isoformat()):
        update(FeaturesMonthly(), tag_date, username)
        update(TargetsMonthly(), tag_date, username)


def update_one(dataset: str, username: str) -> None:
    """
    Update one dataset.

    Args:
        dataset (str): Dataset to update.
        username (str): Username to use.

    Raises:
        ValueError: Unknown dataset.
    """
    tag_date = date.today() - timedelta(days=1)
    datasets = {
        "index-constituents-sp500": IndexConstituentsSP500(),
        "earnings-sp500": EarningsYF(),
        "earnings-estimate-sp500": EarningsEstimateYF(),
        "eps-revisions-sp500": EPSRevisionsYF(),
        "eps-trend-sp500": EPSTrendYF(),
        "news-sp500": NewsYF(),
        "revenue-estimate-sp500": RevenueEstimateYF(),
        "timeseries-daily-sp500": TimeseriesDailyYF(),
        "features-monthly-sp500": FeaturesMonthly(),
        "targets-monthly-sp500": TargetsMonthly(),
    }
    if dataset not in datasets:
        raise ValueError(f"Unknown dataset {dataset}")
    update(datasets[dataset], tag_date, username)


@click.command()
@click.option("--dataset", default="all", help="Dataset to update")
@click.option("--username", default="edarchimbaud", help="Username to use")
def main(dataset: str, username: str):
    """
    Main function.
    """
    if dataset == "all":
        update_all(username)
    else:
        update_one(dataset, username)


if __name__ == "__main__":
    main()
