from datetime import date, timedelta

import click

from systematic_trading.features.predictors.predictors_monthly import PredictorsMonthly
from systematic_trading.features.targets.targets_monthly import TargetsMonthly


@click.command()
@click.option("--username", default="paperswithbacktest", help="Username to use")
def main(suffix: str, username: str):
    tag_date = date.today() - timedelta(days=3)
    print("Updating feature and target datasets...")
    features = {
        "predictors-monthly-stocks": PredictorsMonthly(
            suffix="stocks", tag_date=tag_date, username=username
        ),
        "targets-monthly-stocks": TargetsMonthly(
            suffix="stocks", tag_date=tag_date, username=username
        ),
    }
    for name in features:
        features[name].set_dataset_df()
        features[name].to_hf_datasets()


if __name__ == "__main__":
    main()
