import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error


class MachineLearningApproach:
    def __init__(self, X, Y, train_size=0.8, model="linear"):
        """
        Initialize MachineLearningApproach object with two input arrays X and Y and parameters train_size and model.

        :param X: numpy array representing the prices of stock X
        :param Y: numpy array representing the prices of stock Y
        :param train_size: float representing the proportion of data to use for training (default is 0.8)
        :param model: str representing the type of model to use for prediction (default is 'linear', options are 'linear' or 'rf')
        """
        self.X = X
        self.Y = Y
        self.train_size = train_size
        self.model = model

    def generate_features(self):
        """
        Generate features for machine learning approach.

        :return: pandas DataFrame representing the features for machine learning
        """
        # Calculate spread and z-score of spread
        spread = self.X - self.Y
        mean_spread = spread.mean()
        std_spread = spread.std()
        zscore = (spread - mean_spread) / std_spread

        # Calculate lagged spread
        lagged_spread = pd.DataFrame({"spread": spread, "spread_lag1": spread.shift(1)})
        lagged_spread.dropna(inplace=True)

        # Calculate rolling statistics of spread
        roll_mean = spread.rolling(window=10).mean()
        roll_std = spread.rolling(window=10).std()

        # Combine features into one DataFrame
        features = pd.concat([zscore, lagged_spread, roll_mean, roll_std], axis=1)
        features.dropna(inplace=True)

        return features

    def fit(self):
        """
        Fit machine learning model to training data.

        :return: fitted machine learning model
        """
        # Generate features for machine learning
        features = self.generate_features()

        # Split data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            features.drop("spread", axis=1),
            features["spread"],
            train_size=self.train_size,
        )

        # Fit machine learning model
        if self.model == "linear":
            model = LinearRegression()
        elif self.model == "rf":
            model = RandomForestRegressor(n_estimators=100)
        else:
            raise ValueError("Invalid model type")

        model.fit(X_train, y_train)

        # Evaluate model on testing set
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print("MSE:", mse)

        return model

    def trade(self, threshold):
        """
        Execute trade based on machine learning approach.

        :param threshold: float representing the threshold for entry/exit positions
        :return: numpy array representing the trading positions for X and Y
        """
        # Generate features for machine learning
        features = self.generate_features()

        # Fit machine learning model
        model = self.fit()

        # Generate predictions based on fitted model
        predictions = pd.Series(
            model.predict(features.drop("spread", axis=1)), index=features.index
        )

        # Determine entry and exit positions based on predictions and threshold
        long_entries = predictions <= -threshold
        short_entries = predictions >= threshold

        # Set positions based on entry and exit conditions
        positions = np.zeros(len(predictions))
        positions[long_entries] = 1
        positions[short_entries] = -1

        return positions
