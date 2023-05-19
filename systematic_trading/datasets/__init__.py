from datetime import date

import click
from datasets import Dataset
from earnings_yf import EarningsYF
from earnings_estimate_yf import EarningsEstimateYF
from eps_revisions_yf import EPSRevisionsYF
from eps_trend_yf import EPSTrendYF
from index_constituents_sp500 import IndexConstituentsSP500
from news_yf import NewsYF
from revenue_estimate_yf import RevenueEstimateYF
from timeseries_daily_yf import TimeseriesDailyYF


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
    crawl_all_datasets()  # pylint: disable=no-value-for-parameter@
