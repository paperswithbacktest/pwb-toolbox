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


def update(dataset: Dataset, tag_date: date):
    """
    Crawl the data.
    """
    dataset.suffix = "sp500"
    dataset.tag_date = tag_date
    dataset.username = "edarchimbaud"
    try:
        dataset.update()
    except ValueError as err:
        print(err)


def update_all_datasets():
    """
    Main function.
    """

    tag_date = date.today() - timedelta(days=1)

    update(IndexConstituentsSP500(), tag_date)

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
        futures = [executor.submit(update, dataset, tag_date) for dataset in datasets]
        concurrent.futures.wait(futures)

    update(FeaturesMonthly(), tag_date)
    update(TargetsMonthly(), tag_date)


if __name__ == "__main__":
    update_all_datasets()
