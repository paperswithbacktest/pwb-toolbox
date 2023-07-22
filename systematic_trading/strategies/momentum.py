from datetime import datetime
from dateutil import relativedelta
import os

import backtrader as bt
import backtrader.feeds as btfeeds
from datasets import load_dataset
import matplotlib.pyplot as plt
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
        print(f"{dt.isoformat()},{txt}")

    def is_first_business_day(self, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        first_day = dt.replace(day=1)
        first_business_day = pd.date_range(first_day, periods=1, freq="BMS")[0]
        return dt == first_business_day.date()

    def next(self):
        """
        Execute trades based on the momentum strategy.
        """
        if not self.is_first_business_day():
            return

        # Calculate returns for all stocks
        self.ret = np.array(
            [
                (d.close[-20] / d.close[-252] - 1 if len(d) > 252 else np.NaN)
                for d in self.datas
            ]
        )
        self.log(self.broker.getvalue())

        # Count the number of stocks that have a valid momentum predictor
        num_stocks = np.count_nonzero(~np.isnan(self.ret))

        # Compute the quantile thresholds
        long_threshold = np.nanquantile(self.ret, self.params.long_quantile)
        short_threshold = np.nanquantile(self.ret, self.params.short_quantile)

        for i, d in enumerate(self.datas):
            if self.ret[i] > long_threshold:  # Long the top quantile stocks
                self.order_target_percent(
                    data=d,
                    target=0.7 / num_stocks,
                )
            elif self.ret[i] < short_threshold:  # Short the bottom quantile stocks
                self.order_target_percent(
                    data=d,
                    target=-0.7 / num_stocks,
                )
            else:  # Close positions that don't meet the long or short criteria
                self.close(data=d)


class CashNav(bt.analyzers.Analyzer):
    """
    Analyzer returning cash and market values
    """

    def create_analysis(self):
        self.rets = {}
        self.vals = 0.0

    def notify_cashvalue(self, cash, value):
        self.vals = (
            self.strategy.datetime.datetime(),
            cash,
            value,
        )
        self.rets[len(self)] = self.vals

    def get_analysis(self):
        return self.rets


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
    cerebro.broker.set_cash(1000000)

    starting_date = datetime(1990, 1, 1)

    # Add Data Feeds to Cerebro
    for _, symbol in enumerate(tqdm(symbols)):
        df_symbol = df[df["symbol"] == symbol].copy()
        if df_symbol["date"].min() > starting_date:
            continue
        factor = df_symbol["adj_close"] / df_symbol["close"]
        df_symbol["open"] = df_symbol["open"] * factor
        df_symbol["high"] = df_symbol["high"] * factor
        df_symbol["low"] = df_symbol["low"] * factor
        df_symbol["close"] = df_symbol["close"] * factor
        df_symbol.drop(["symbol", "adj_close"], axis=1, inplace=True)
        df_symbol.set_index("date", inplace=True)
        data = btfeeds.PandasData(dataname=df_symbol)
        cerebro.adddata(data, name=symbol)

    # Add Strategy to Cerebro
    cerebro.addstrategy(
        MomentumStrategy, long_quantile=0.8, short_quantile=0.2
    )  # Adjust parameters as desired

    cerebro.addanalyzer(CashNav, _name="cash_nav")

    # Run the Strategy
    results = cerebro.run()
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())

    dictionary = results[0].analyzers.getbyname("cash_nav").get_analysis()
    df = pd.DataFrame(dictionary).T
    df.columns = ["Date", "Cash", "Nav"]
    df.set_index("Date", inplace=True)
    df.loc[df.index >= starting_date, ["Nav"]].plot()
    plt.show()


if __name__ == "__main__":
    main()
