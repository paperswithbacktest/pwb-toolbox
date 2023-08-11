from datetime import date, datetime, timedelta
import os
from typing import List

import click
from tqdm import tqdm
from twilio.rest import Client

from systematic_trading.datasets.dataset import Dataset
from systematic_trading.datasets.index_constituents import IndexConstituents
from systematic_trading.datasets.index_constituents.sp500 import SP500
from systematic_trading.datasets.index_constituents.stocks import Stocks
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


def send_sms(message: str):
    """
    Send a SMS using Twilio.
    """
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    client = Client(account_sid, auth_token)
    client.messages.create(
        to=os.environ["TWILIO_TO"],
        from_=os.environ["TWILIO_FROM"],
        body=message,
    )


def download_index_constituents(tag_date: date, username: str):
    """
    Download index constituents.
    """
    index_constituents = {
        "sp500": SP500(tag_date=tag_date, username=username),
        "stocks": Stocks(tag_date=tag_date, username=username),
    }
    for name in index_constituents:
        if not index_constituents[name].check_file_exists(tag=tag_date.isoformat()):
            index_constituents[name].set_dataset_df()
            index_constituents[name].to_hf_datasets()


def download_raw_datasets(tag_date: date, username: str):
    """
    Download raw datasets.
    """
    suffix = "stocks"
    raw_datasets = {
        f"earnings-{suffix}": Earnings(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"earnings-estimate-{suffix}": EarningsEstimate(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"earnings-forecast-{suffix}": EarningsForecast(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"earnings-surprise-{suffix}": EarningsSurprise(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"extended-trading-{suffix}": ExtendedTrading(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"eps-revisions-{suffix}": EPSRevisions(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"eps-trend-{suffix}": EPSTrend(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"news-{suffix}": News(suffix=suffix, tag_date=tag_date, username=username),
        f"revenue-estimate-{suffix}": RevenueEstimate(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"short-interest-{suffix}": ShortInterest(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"timeseries-daily-{suffix}": TimeseriesDaily(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"timeseries-1mn-{suffix}": Timeseries1mn(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    dataset_names = [
        name
        for name in raw_datasets
        if not raw_datasets[name].check_file_exists(tag=tag_date.isoformat())
    ]
    for name in dataset_names:
        raw_datasets[name].load_frames()
    index_constituents = Stocks(tag_date=tag_date, username=username)
    for symbol in tqdm(index_constituents.symbols):
        for name in dataset_names:
            if symbol in raw_datasets[name].frames:
                continue
            raw_datasets[name].append_frame(symbol)
            raw_datasets[name].save_frames()
    for name in dataset_names:
        raw_datasets[name].set_dataset_df()
        raw_datasets[name].to_hf_datasets()


@click.command()
@click.option("--mode", default="", help="Mode to use, daily / on-demand")
@click.option("--username", default="edarchimbaud", help="Username to use")
def main(mode: str, username: str):
    """
    Main function.
    """
    if mode == "daily" or mode == "daily-force":
        now = datetime.now()
        if now.hour > 21:
            tag_date = date.today()
        elif now.hour < 10 or mode == "daily-force":
            tag_date = date.today() - timedelta(days=1)
        else:
            raise ValueError("This script should be run between 21:00 and 10:00")
        print("Updating index constituents...")
        download_index_constituents(tag_date=tag_date, username=username)
        print("Updating raw datasets...")
        download_raw_datasets(tag_date=tag_date, username=username)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        send_sms(f"Error: {e}")
