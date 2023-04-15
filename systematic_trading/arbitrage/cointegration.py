import numpy as np
import pandas as pd
import statsmodels.api as sm


class CointegrationApproach:
    def __init__(self, X, Y):
        """
        Initialize CointegrationApproach object with two input arrays X and Y.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        """
        self.X = X
        self.Y = Y

    def cointegration_test(self):
        """
        Perform cointegration test to determine if X and Y are cointegrated.

        :return: boolean indicating whether X and Y are cointegrated
        """
        # Perform cointegration test using OLS regression
        X = sm.add_constant(self.X)
        results = sm.OLS(self.Y, X).fit()
        residuals = results.resid
        adf_test = sm.tsa.stattools.adfuller(residuals)

        # Determine if residuals are stationary (i.e. if X and Y are cointegrated)
        if adf_test[1] < 0.05:
            return True
        else:
            return False

    def trade(self, threshold):
        """
        Execute trade based on cointegration of X and Y.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Perform OLS regression to determine cointegrated spread
        X = sm.add_constant(self.X)
        results = sm.OLS(self.Y, X).fit()
        spread = self.Y - results.params[1] * self.X

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
