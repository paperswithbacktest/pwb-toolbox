from datetime import date, datetime, timedelta
import os
from pprint import pprint
from typing import List

import click
import pytz
from tqdm import tqdm
from twilio.rest import Client

from systematic_trading.datasets import Dataset
from systematic_trading.datasets.perimeters import Perimeter
from systematic_trading.datasets.perimeters.sp500 import SP500
from systematic_trading.datasets.perimeters.stocks import Stocks
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
from systematic_trading.helpers import send_sms


def download_perimeters(tag_date: date, username: str):
    """
    Download index constituents.
    """
    perimeters = {
        "sp500": SP500(tag_date=tag_date, username=username),
        "stocks": Stocks(tag_date=tag_date, username=username),
    }
    for perimeter in perimeters.values():
        if not perimeter.check_file_exists(tag=tag_date.isoformat()):
            perimeter.set_dataset_df()
            perimeter.to_hf_datasets()


def download_raw_datasets(raw_datasets: dict, tag_date: date, username: str):
    """
    Download raw datasets.
    """
    raw_datasets_to_update = {
        k: v
        for k, v in raw_datasets.items()
        if not v.check_file_exists(tag=tag_date.isoformat())
    }
    for name in raw_datasets_to_update:
        raw_datasets_to_update[name].load_frames()
    perimeter = Stocks(tag_date=tag_date, username=username)
    for symbol in tqdm(perimeter.symbols):
        for name in raw_datasets_to_update:
            if symbol in raw_datasets_to_update[name].frames:
                continue
            raw_datasets_to_update[name].append_frame(symbol)
            raw_datasets_to_update[name].save_frames()
    for name in raw_datasets_to_update:
        raw_datasets_to_update[name].set_dataset_df()
        raw_datasets_to_update[name].to_hf_datasets()


def download_raw_datasets_after_open(suffix: str, tag_date: date, username: str):
    """
    Download raw datasets after open.
    """
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
        f"eps-revisions-{suffix}": EPSRevisions(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"eps-trend-{suffix}": EPSTrend(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"extended-trading-{suffix}": ExtendedTrading(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"revenue-estimate-{suffix}": RevenueEstimate(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"short-interest-{suffix}": ShortInterest(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    download_raw_datasets(
        raw_datasets=raw_datasets,
        tag_date=tag_date,
        username=username,
    )


def download_raw_datasets_after_close(suffix: str, tag_date: date, username: str):
    raw_datasets = {
        f"news-{suffix}": News(suffix=suffix, tag_date=tag_date, username=username),
        f"timeseries-daily-{suffix}": TimeseriesDaily(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        f"timeseries-1mn-{suffix}": Timeseries1mn(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    download_raw_datasets(
        raw_datasets=raw_datasets,
        tag_date=tag_date,
        username=username,
    )


def download(slot: str, timeoffset: int = 0):
    """
    Main function.
    """
    now = datetime.now()
    nyc_timezone = pytz.timezone("America/New_York")
    nyc_time = now.astimezone(nyc_timezone)
    us_market_open_time = nyc_time.replace(hour=9, minute=30, second=0, microsecond=0)
    us_market_close_time = nyc_time.replace(hour=16, minute=0, second=0, microsecond=0)
    tag_date = date.today() + timedelta(days=timeoffset)
    username = os.environ.get("HF_USERNAME")
    pprint(
        {
            "nyc_time": nyc_time.isoformat(),
            "tag_date": tag_date.isoformat(),
            "username": username,
        }
    )
    suffix = "stocks"
    if (slot == "" and nyc_time < us_market_open_time) or slot == "before-open":
        print("Downloading before open")
        download_perimeters(tag_date=tag_date, username=username)
    elif (
        slot == ""
        and nyc_time > us_market_open_time
        and nyc_time < us_market_close_time
    ) or slot == "after-open":
        print("Downloading after open")
        download_raw_datasets_after_open(
            suffix=suffix, tag_date=tag_date, username=username
        )
    elif (slot == "" and nyc_time > us_market_close_time) or slot == "after-close":
        print("Downloading after close")
        download_raw_datasets_after_close(
            suffix=suffix, tag_date=tag_date, username=username
        )
    else:
        raise ValueError("Invalid time slot")


@click.command()
@click.option("--mode", default="debug", help="debug, production")
@click.option("--slot", default="", help="before-open, after-open, after-close")
@click.option("--timeoffset", default=0, help="time offset")
def main(mode: str, slot: str, timeoffset: int):
    if mode == "debug":
        download(slot=slot, timeoffset=timeoffset)
    elif mode == "production":
        try:
            download(slot=slot, timeoffset=timeoffset)
        except Exception as e:
            print(e)
            send_sms(f"Error: {e}")


if __name__ == "__main__":
    main()
