from datetime import date, timedelta

import click

from systematic_trading.features.signals.signals_monthly import SignalsMonthly
from systematic_trading.features.targets.targets_monthly import TargetsMonthly


@click.command()
@click.option("--suffix", default="sp500", help="Suffix to use")
@click.option("--username", default="edarchimbaud", help="Username to use")
def main(suffix: str, username: str):
    tag_date = date.today() - timedelta(days=3)
    print("Updating feature and target datasets...")
    features = {
        "signals-monthly-sp500": SignalsMonthly(
            suffix=suffix, tag_date=tag_date, username=username
        ),
        "targets-monthly-sp500": TargetsMonthly(
            suffix=suffix, tag_date=tag_date, username=username
        ),
    }
    for name in features:
        features[name].set_dataset_df()
        features[name].to_hf_datasets()


if __name__ == "__main__":
    main()
