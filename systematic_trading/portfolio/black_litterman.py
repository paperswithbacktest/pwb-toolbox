import numpy as np
from scipy.optimize import minimize

class BlackLitterman:
    def __init__(self, returns, market_caps, risk_free_rate, tau=0.05, delta=2.5, confidences=None, views=None):
        self.returns = returns
        self.market_caps = market_caps
        self.risk_free_rate = risk_free_rate
        self.tau = tau
        self.delta = delta
        self.confidences = confidences
        self.views = views
        self.num_assets = returns.shape[1]
        self.pi = None
        self.sigma = None
        self.omega = None
        self.P = None
        self.Q = None
        
    def fit(self):
        # Compute equilibrium returns and covariance matrix
        market_weights = self.market_caps / np.sum(self.market_caps)
        self.pi = np.dot(self.returns.T, market_weights)
        self.sigma = np.cov(self.returns, rowvar=False)
        
        # Compute uncertainty matrix
        self.omega = self.delta * np.diag(np.diag(np.dot(np.dot(market_weights.reshape(-1,1), market_weights.reshape(1,-1)), self.sigma)))
        
        # Compute posterior expected returns and covariance matrix
        posterior_sigma = np.linalg.inv(np.linalg.inv(self.tau * self.sigma) + np.dot(np.dot(self.P.T, np.linalg.inv(self.omega)), self.P))
        posterior_pi = np.dot(posterior_sigma, np.dot(np.linalg.inv(self.tau * self.sigma), self.pi) + np.dot(np.dot(self.P.T, np.linalg.inv(self.omega)), self.Q))
        
        # Compute optimal portfolio weights
        def objective_function(weights):
            portfolio_variance = np.dot(weights.T, np.dot(posterior_sigma, weights))
            return portfolio_variance
        
        constraint = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        bounds = [(0, None) for i in range(self.num_assets)]
        x0 = np.ones(self.num_assets) / self.num_assets
        result = minimize(objective_function, x0, method='SLSQP', constraints=constraint, bounds=bounds)
        
        if result.success:
            self.weights = result.x
        else:
            raise ValueError(result.message)
    
    def set_views(self, confidences, views):
        self.confidences = confidences
        self.views = views
        
        # Compute views matrix and error matrix
        self.P = np.zeros((len(views), self.num_assets))
        for i, view in enumerate(views):
            asset, view_return = view
            self.P[i, asset] = 1
        self.Q = np.array([view[1] for view in views])
        self.omega = self.delta * np.diag(np.diag(np.dot(np.dot(self.P, self.sigma), self.P.T))) * np.array(confidences)
        
    def optimize(self):
        # Compute equilibrium returns and covariance matrix
        market_weights = self.market_caps / np.sum(self.market_caps)
        self.pi = np.dot(self.returns.T, market_weights)
        self.sigma = np.cov(self.returns, rowvar=False)
        
        # Compute uncertainty matrix
        if self.views is None:
            self.omega = self.delta * np.diag(np.diag(np.dot(np.dot(market_weights.reshape(-1,1), market_weights.reshape(1,-1)), self.sigma)))
        else:
            self.omega = self.delta * np.diag(np.diag(np.dot(np.dot(self.P, self.sigma), self.P.T))) * np.array(self.confidences)
        
