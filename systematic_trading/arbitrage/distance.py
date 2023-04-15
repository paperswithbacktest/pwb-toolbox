import numpy as np


class DistanceApproach:
    def __init__(self, X, Y):
        """
        Initialize DistanceApproach object with two input arrays X and Y.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        """
        self.X = X
        self.Y = Y

    def zscore(self):
        """
        Calculate the z-score of the spread between X and Y.

        :return: numpy array representing the z-score of the spread
        """
        # Calculate the spread between X and Y
        spread = self.X - self.Y

        # Calculate the mean and standard deviation of the spread
        mean_spread = np.mean(spread)
        std_spread = np.std(spread)

        # Calculate the z-score of the spread
        zscore = (spread - mean_spread) / std_spread

        return zscore

    def trade(self, zscore, threshold):
        """
        Execute trade based on z-score of the spread.

        :param zscore: numpy array representing the z-score of the spread
        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
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
