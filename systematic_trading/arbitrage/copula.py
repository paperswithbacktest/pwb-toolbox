import numpy as np
import pandas as pd
from scipy import stats
from copulae import GaussianCopula


class CopulaApproach:
    def __init__(self, X, Y):
        """
        Initialize CopulaApproach object with two input arrays X and Y.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        """
        self.X = X
        self.Y = Y

    def fit(self):
        """
        Fit Gaussian copula to X and Y.

        :return: copulae GaussianCopula object
        """
        # Define margins for X and Y using empirical CDF
        x_marginal = stats.uniform(0, 1).ppf(stats.rankdata(self.X) / (len(self.X) + 1))
        y_marginal = stats.uniform(0, 1).ppf(stats.rankdata(self.Y) / (len(self.Y) + 1))

        # Fit Gaussian copula to X and Y
        copula = GaussianCopula(dim=2)
        copula.fit([x_marginal, y_marginal])

        return copula

    def trade(self, threshold):
        """
        Execute trade based on copula approach.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Fit Gaussian copula to X and Y
        copula = self.fit()

        # Generate simulated copula values
        sim_copula = copula.simulate(len(self.X))

        # Transform simulated copula values to uniform marginals
        sim_marginals = np.apply_along_axis(
            lambda x: np.array([stats.norm.cdf(x[0]), stats.norm.cdf(x[1])]),
            axis=1,
            arr=sim_copula,
        )

        # Transform uniform marginals to empirical CDF
        sim_x = stats.uniform(0, 1).isf(sim_marginals[:, 0])
        sim_y = stats.uniform(0, 1).isf(sim_marginals[:, 1])

        # Calculate simulated spread
        sim_spread = sim_x - sim_y

        # Calculate mean and standard deviation of simulated spread
        mean_spread = np.mean(sim_spread)
        std_spread = np.std(sim_spread)

        # Calculate z-score of simulated spread
        zscore = (sim_spread - mean_spread) / std_spread

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
