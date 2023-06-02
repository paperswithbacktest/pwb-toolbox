from datetime import date

from systematic_trading.features.signals.signals_monthly import SignalsMonthly
from systematic_trading.features.targets.targets_monthly import TargetsMonthly


def main():
    tag_date = date.today()
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
