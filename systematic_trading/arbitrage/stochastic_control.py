import numpy as np
import pandas as pd
from scipy.optimize import minimize
from statsmodels.tsa.stattools import adfuller


class StochasticControlApproach:
    def __init__(self, X, Y, delta=0.1, gamma=1, lam=0.01):
        """
        Initialize StochasticControlApproach object with two input arrays X and Y and parameters delta, gamma, and lam.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        :param delta: float representing the cost of trading (default is 0.1)
        :param gamma: float representing the risk aversion coefficient (default is 1)
        :param lam: float representing the regularization parameter (default is 0.01)
        """
        self.X = X
        self.Y = Y
        self.delta = delta
        self.gamma = gamma
        self.lam = lam

    def fit(self):
        """
        Fit stochastic control model to data.

        :return: numpy array representing the optimal trading positions for X and Y
        """
        # Calculate spread and z-score of spread
        spread = self.X - self.Y
        mean_spread = spread.mean()
        std_spread = spread.std()
        zscore = (spread - mean_spread) / std_spread

        # Define objective function for stochastic control optimization
        def objective_function(theta):
            # Calculate optimal trading positions
            positions = np.sign(zscore - theta)

            # Calculate trading costs
            cost = np.sum(np.abs(np.diff(positions)) * self.delta)

            # Calculate expected profit
            profit = np.sum(
                (positions[:-1] * zscore[:-1] - np.abs(np.diff(positions)) * self.delta)
                - self.gamma / 2 * np.square(np.diff(positions))
            )

            # Add regularization term
            objective = -profit + self.lam * np.sum(np.abs(theta))

            return objective

        # Set optimization bounds
        bounds = [(0, 1) for i in range(len(zscore))]

        # Perform optimization
        result = minimize(
            objective_function, np.zeros(len(zscore)), method="L-BFGS-B", bounds=bounds
        )

        # Extract optimal trading positions
        theta = result.x
        positions = np.sign(zscore - theta)

        return positions

    def trade(self, threshold):
        """
        Execute trade based on stochastic control approach.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Fit stochastic control model
        positions = self.fit()

        # Apply Augmented Dickey-Fuller test to spread
        adf_result = adfuller(self.X - self.Y)
        adf_statistic = adf_result[0]
        adf_pvalue = adf_result[1]

        # Determine mean and standard deviation of stationary spread
        mean_spread = (self.X - self.Y).mean()
        std_spread = (self.X - self.Y).std()

        # Calculate z-score of spread
        zscore = ((self.X - self.Y) - mean_spread) / std_spread

        # Determine entry and exit positions based on z-score and threshold
        long_entries = zscore <= -threshold
        short_entries = zscore >= threshold
        exit = abs(zscore) < 0.5

        # Set positions based on entry and exit conditions
        positions[long_entries] = 1
        positions[short_entries] = -1
        positions[exit] = 0

        return positions
