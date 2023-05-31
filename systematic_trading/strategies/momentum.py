from datetime import datetime
from dateutil import relativedelta
import os

import backtrader as bt
import backtrader.feeds as btfeeds
from datasets import load_dataset
import numpy as np
import pandas as pd
import pickle
from tqdm import tqdm


class MomentumStrategy(bt.Strategy):
    """
    A momentum strategy that goes long the top quantile of stocks
    and short the bottom quantile of stocks.
    """

    params = (
        ("long_quantile", 0.8),  # Long quantile threshold (e.g., top 80%)
        ("short_quantile", 0.2),  # Short quantile threshold (e.g., bottom 20%)
    )

    def __init__(self):
        self.ret = np.zeros(len(self.datas))

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}: {txt}")

    def is_first_business_day(self, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        # Check if the date is a weekday (Monday to Friday)
        if dt.weekday() < 5:
            first_day = dt.replace(day=1)
            # Find the first business day in the month
            while first_day.weekday() > 4:  # Skip Saturday (5) and Sunday (6)
                first_day += relativedelta.relativedelta(days=1)
            # Compare the dates
            if dt == first_day:
                return True
        return False

    def next(self):
        """
        Execute trades based on the momentum strategy.
        """
        if not self.is_first_business_day():
            return
        self.log(self.broker.getvalue())

        # Calculate returns for all stocks
        self.ret = np.array(
            [
                (d.close[-20] / d.close[-252] - 1 if len(d) > 252 else np.NaN)
                for d in self.datas
            ]
        )

        # Count the number of stocks that have a valid momentum signal
        num_stocks = np.count_nonzero(~np.isnan(self.ret))

        # Compute the quantile thresholds
        long_threshold = np.nanquantile(self.ret, self.params.long_quantile)
        short_threshold = np.nanquantile(self.ret, self.params.short_quantile)

        for i, d in enumerate(self.datas):
            if self.ret[i] > long_threshold:  # Long the top quantile stocks
                self.order_target_percent(
                    data=d,
                    target=1.0 / num_stocks,
                )
            elif self.ret[i] < short_threshold:  # Short the bottom quantile stocks
                self.order_target_percent(
                    data=d,
                    target=-1.0 / num_stocks,
                )
            else:  # Close positions that don't meet the long or short criteria
                self.close(data=d)


def main():
    # Load Data
    path = os.path.join("/tmp", "momentum.pkl")
    if os.path.exists(path):
        df = pickle.load(open(path, "rb"))
    else:
        dataset = load_dataset("edarchimbaud/timeseries-daily-sp500", split="train")
        df = pd.DataFrame(dataset)
        pickle.dump(df, open(path, "wb"))

    # Data Preparation
    symbols = df["symbol"].unique()
    df["date"] = pd.to_datetime(df["date"])

    # Create a Cerebro object
    cerebro = bt.Cerebro()

    # Add Data Feeds to Cerebro
    for symbol in tqdm(symbols):
        df_symbol = df[df["symbol"] == symbol]
        if df_symbol.date.iloc[0] > datetime(2000, 1, 1):
            continue
        data = btfeeds.PandasData(dataname=df_symbol, datetime="date")
        cerebro.adddata(data)

    # Add Strategy to Cerebro
    cerebro.addstrategy(
        MomentumStrategy, long_quantile=0.8, short_quantile=0.2
    )  # Adjust parameters as desired

    # Run the Strategy
    cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

    # Plot the Results
    # cerebro.plot()


if __name__ == "__main__":
    main()
