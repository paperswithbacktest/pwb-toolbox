from datetime import date, datetime, timedelta
from typing import List

import click
from tqdm import tqdm

from systematic_trading.datasets.dataset import Dataset
from systematic_trading.datasets.index_constituents import IndexConstituents
from systematic_trading.datasets.index_constituents.sp500 import SP500
from systematic_trading.datasets.knowledge_graph.stocks import Stocks
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


@click.command()
@click.option("--mode", default="", help="Mode to use, daily / on-demand")
@click.option("--username", default="edarchimbaud", help="Username to use")
def main(mode: str, username: str):
    """
    Main function.
    """
    if mode == "daily":
        now = datetime.now()
        if now.hour > 21:
            tag_date = date.today()
        elif now.hour < 10:
            tag_date = date.today() - timedelta(days=1)
        else:
            raise ValueError("This script should be run between 21:00 and 10:00")
        tag = tag_date.isoformat()
        print("Updating index constituents...")
        index_constituents = SP500(tag_date=tag_date, username=username)
        if not index_constituents.check_file_exists(tag=tag):
            index_constituents.set_dataset_df()
            index_constituents.to_hf_datasets()
        print("Updating raw datasets...")
        raw_datasets = {
            "earnings-stocks": Earnings(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "earnings-estimate-stocks": EarningsEstimate(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "earnings-forecast-stocks": EarningsForecast(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "earnings-surprise-stocks": EarningsSurprise(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "extended-trading-stocks": ExtendedTrading(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "eps-revisions-stocks": EPSRevisions(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "eps-trend-stocks": EPSTrend(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "news-stocks": News(suffix="stocks", tag_date=tag_date, username=username),
            "revenue-estimate-stocks": RevenueEstimate(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "short-interest-stocks": ShortInterest(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "timeseries-daily-stocks": TimeseriesDaily(
                suffix="stocks", tag_date=tag_date, username=username
            ),
            "timeseries-1mn-stocks": Timeseries1mn(
                suffix="stocks", tag_date=tag_date, username=username
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
    elif mode == "on-demand":
        print("Updating list of stocks...")
        stocks = Stocks(tag_date=date.today(), username=username)
        stocks.set_dataset_df()
        stocks.to_hf_datasets()


if __name__ == "__main__":
    main()
