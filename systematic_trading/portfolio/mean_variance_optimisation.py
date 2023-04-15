import numpy as np
from scipy.optimize import minimize

class MeanVarianceOptimization:
    def __init__(self, returns, target_return=None, method='min_variance', constraints=None, risk_aversion=None):
        self.returns = returns
        self.target_return = target_return
        self.method = method
        self.constraints = constraints
        self.risk_aversion = risk_aversion
        self.num_assets = returns.shape[1]
        self.weights = None
        
    def optimize(self):
        # Objective function to minimize
        def objective_function(weights):
            if self.method == 'inverse_variance':
                portfolio_variance = np.dot(weights.T, np.linalg.inv(np.cov(self.returns, rowvar=False)).dot(weights))
                return 1 / portfolio_variance
            elif self.method == 'min_variance':
                portfolio_variance = np.dot(weights.T, np.cov(self.returns, rowvar=False)).dot(weights)
                return portfolio_variance
            elif self.method == 'quadratic_utility':
                portfolio_return = np.dot(weights.T, self.returns.mean(axis=0))
                portfolio_variance = np.dot(weights.T, np.cov(self.returns, rowvar=False)).dot(weights)
                return portfolio_return - 0.5 * self.risk_aversion * portfolio_variance
            elif self.method == 'max_sharpe':
                portfolio_return = np.dot(weights.T, self.returns.mean(axis=0))
                portfolio_variance = np.dot(weights.T, np.cov(self.returns, rowvar=False)).dot(weights)
                return -(portfolio_return - self.target_return) / np.sqrt(portfolio_variance)
            elif self.method == 'efficient_risk':
                portfolio_variance = np.dot(weights.T, np.cov(self.returns, rowvar=False)).dot(weights)
                return np.sqrt(portfolio_variance) - self.risk_aversion * self.target_return
            elif callable(self.method):
                return self.method(weights)
            else:
                raise ValueError('Invalid method specified')
        
        # Constraint on weights
        if self.constraints is None:
            constraint = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
            bounds = [(0, None) for i in range(self.num_assets)]
        else:
            constraint = self.constraints
            bounds = [(0, None) for i in range(self.num_assets)]
        
        # Constraint on target return
        if self.target_return is not None:
            constraint_return = {'type': 'eq', 'fun': lambda x: np.dot(x.T, self.returns.mean(axis=0)) - self.target_return}
            constraint = [constraint, constraint_return]
        
        # Initial guess for weights
        x0 = np.ones(self.num_assets) / self.num_assets
        
        # Optimisation
        result = minimize(objective_function, x0, method='SLSQP', constraints=constraint, bounds=bounds)
        
        if result.success:
            self.weights = result.x
        else:
            raise ValueError(result.message)
