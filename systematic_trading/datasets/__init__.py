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


def update_all_datasets():
    """
    Main function.
    """

    def update(dataset: Dataset, tag_date: date):
        """
        Crawl the data.
        """
        dataset.suffix = "sp500"
        dataset.tag_date = tag_date
        dataset.username = "edarchimbaud"
        try:
            dataset.update()
        except ValueError as e:
            print(e)

    tag_date = date.today() - timedelta(days=1)
    update(dataset=IndexConstituentsSP500(), tag_date=tag_date)
    update(dataset=EarningsYF(), tag_date=tag_date)
    update(dataset=EarningsEstimateYF(), tag_date=tag_date)
    update(dataset=EPSRevisionsYF(), tag_date=tag_date)
    update(dataset=EPSTrendYF(), tag_date=tag_date)
    update(dataset=NewsYF(), tag_date=tag_date)
    update(dataset=RevenueEstimateYF(), tag_date=tag_date)
    update(dataset=TimeseriesDailyYF(), tag_date=tag_date)
    update(dataset=FeaturesMonthly(), tag_date=tag_date)
    update(dataset=TargetsMonthly(), tag_date=tag_date)


if __name__ == "__main__":
    update_all_datasets()
