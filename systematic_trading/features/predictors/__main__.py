from datetime import date

from systematic_trading.features.predictors.predictors_monthly import PredictorsMonthly
from systematic_trading.features.targets.targets_monthly import TargetsMonthly


def main():
    tag_date = date.today()
    print("Updating feature and target datasets...")
    features = {
        "predictors-monthly-sp500": PredictorsMonthly(
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
