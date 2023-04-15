import numpy as np


class OnlinePortfolioSelection:
    def __init__(self, num_assets, eta, gamma):
        self.num_assets = num_assets
        self.eta = eta
        self.gamma = gamma
        self.weights = np.ones(num_assets) / num_assets
        self.past_returns = []

    def update(self, returns):
        self.past_returns.append(returns)
        past_returns_matrix = np.array(self.past_returns)
        past_returns_matrix[past_returns_matrix < 0] = 0
        total_past_returns = np.sum(past_returns_matrix, axis=0)
        total_past_returns /= np.sum(total_past_returns)
        self.weights *= np.exp(self.eta * returns * total_past_returns)
        self.weights /= np.sum(self.weights)

    def get_weights(self):
        return self.weights
