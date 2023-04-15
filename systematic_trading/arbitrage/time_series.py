import numpy as np
import pandas as pd
import statsmodels.api as sm


class TimeSeriesApproach:
    def __init__(self, X, Y):
        """
        Initialize TimeSeriesApproach object with two input arrays X and Y.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        """
        self.X = X
        self.Y = Y

    def fit(self):
        """
        Fit time series model to the spread between X and Y.

        :return: statsmodels ARMA model object
        """
        # Calculate spread between X and Y
        spread = self.X - self.Y

        # Fit ARMA model to spread
        model = sm.tsa.ARMA(spread, order=(1, 1)).fit()

        return model

    def trade(self, threshold):
        """
        Execute trade based on time series model of mean-reverting process.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Calculate spread between X and Y
        spread = self.X - self.Y

        # Fit ARMA model to spread
        model = sm.tsa.ARMA(spread, order=(1, 1)).fit()

        # Calculate forecasted spread using ARMA model
        forecast = model.forecast()[0]

        # Calculate mean and standard deviation of spread
        mean_spread = np.mean(spread)
        std_spread = np.std(spread)

        # Calculate z-score of spread
        zscore = (spread - mean_spread) / std_spread

        # Determine entry and exit positions based on z-score and threshold
        long_entries = zscore <= -threshold
        short_entries = zscore >= threshold
        exit = abs(zscore) < 0.5
        long_exit = zscore >= -0.5
        short_exit = zscore <= 0.5

        # Set positions based on entry and exit conditions
        positions = np.zeros(len(zscore))
        positions[long_entries] = 1
        positions[short_entries] = -1
        positions[exit] = 0
        positions[long_exit] = 0
        positions[short_exit] = 0

        return positions
