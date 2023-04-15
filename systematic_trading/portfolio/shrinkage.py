import numpy as np
from scipy.optimize import minimize

class Shrinkage:
    def __init__(self, returns):
        self.returns = returns
        self.num_assets = returns.shape[1]
        self.sample_cov = np.cov(returns, rowvar=False)

    def basic_shrinkage(self, delta):
        shrinkage_cov = delta * self.sample_cov + (1 - delta) * np.eye(self.num_assets) * np.trace(self.sample_cov) / self.num_assets
        return shrinkage_cov

    def lw_shrinkage(self):
        variances = np.diag(self.sample_cov)
        target = np.mean(variances)
        def error_function(delta):
            return np.sum((variances - delta * target)**2) / self.num_assets
        result = minimize(error_function, 0.5)
        shrinkage_cov = result.x[0] * self.sample_cov + (1 - result.x[0]) * np.eye(self.num_assets) * np.trace(self.sample_cov) / self.num_assets
        return shrinkage_cov

    def oas_shrinkage(self):
        variances = np.diag(self.sample_cov)
        target = np.mean(variances)
        precision_matrix = np.linalg.inv(self.sample_cov)
        scaled_precision_matrix = np.dot(np.dot(np.sqrt(np.diag(precision_matrix)), self.sample_cov), np.sqrt(np.diag(precision_matrix)))
        target_tr = np.trace(scaled_precision_matrix) / self.num_assets
        delta = target_tr / target
        rho = 0.05
        scaled_shrinkage_cov = delta * self.sample_cov + (1 - delta) * np.eye(self.num_assets) * np.trace(self.sample_cov) / self.num_assets
        shrinkage_cov = rho * scaled_shrinkage_cov + (1 - rho) * self.sample_cov
        return shrinkage_cov

    def get_shrinkage(self, method='basic', delta=None):
        if method == 'basic':
            return self.basic_shrinkage(delta)
        elif method == 'lw':
            return self.lw_shrinkage()
        elif method == 'oas':
            return self.oas_shrinkage()
        else:
            raise ValueError("Invalid shrinkage method. Choose from 'basic', 'lw', or 'oas'.")
