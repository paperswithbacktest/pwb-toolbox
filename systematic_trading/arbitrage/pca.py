import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima_process import ArmaProcess


class PCAApproach:
    def __init__(self, X, Y, n_components=1):
        """
        Initialize PCAApproach object with two input arrays X and Y and parameter n_components.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        :param n_components: int representing the number of principal components to use for the spread
        """
        self.X = X
        self.Y = Y
        self.n_components = n_components

    def fit(self):
        """
        Fit PCA model to X and Y to generate spread.

        :return: numpy array representing the PCA spread
        """
        # Combine X and Y into one matrix
        data = np.column_stack((self.X, self.Y))

        # Fit PCA model to data
        pca = PCA(n_components=self.n_components)
        pca.fit(data)

        # Calculate PCA spread
        pca_spread = pca.transform(data)[:, 0]

        return pca_spread

    def trade(self, threshold):
        """
        Execute trade based on PCA approach.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Calculate PCA spread
        pca_spread = self.fit()

        # Fit ARMA model to PCA spread
        ar_model = ArmaProcess(pca_spread).fit(maxlag=1, method="mle", trend="nc")
        ar_coefficient = ar_model.params[1]

        # Apply Augmented Dickey-Fuller test to PCA spread
        adf_result = adfuller(pca_spread)
        adf_statistic = adf_result[0]
        adf_pvalue = adf_result[1]

        # Determine mean and standard deviation of stationary spread
        mean_spread = ar_coefficient / (1 - ar_coefficient) * pca_spread.mean()
        std_spread = np.sqrt(1 / (1 - ar_coefficient**2) * pca_spread.var())

        # Calculate z-score of PCA spread
        zscore = (pca_spread - mean_spread) / std_spread

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
