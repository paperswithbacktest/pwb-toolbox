from datetime import date

import click
from systematic_trading.datasets.dataset import Dataset
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


@click.command()
@click.option("--dataset", default="all", help="Dataset to crawl")
def crawl_all_datasets(dataset: str):
    """
    Main function.
    """

    def crawl(dataset: Dataset, today: date):
        """
        Crawl the data.
        """
        dataset.suffix = "sp500"
        dataset.today = today
        dataset.username = "edarchimbaud"
        try:
            dataset.crawl()
        except ValueError as e:
            print(e)

    today = date.today()
    crawl(dataset=IndexConstituentsSP500(), today=today)
    crawl(dataset=EarningsYF(), today=today)
    crawl(dataset=EarningsEstimateYF(), today=today)
    crawl(dataset=EPSRevisionsYF(), today=today)
    crawl(dataset=EPSTrendYF(), today=today)
    crawl(dataset=NewsYF(), today=today)
    crawl(dataset=RevenueEstimateYF(), today=today)
    crawl(dataset=TimeseriesDailyYF(), today=today)


if __name__ == "__main__":
    crawl_all_datasets()  # pylint: disable=no-value-for-parameter
