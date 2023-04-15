import numpy as np
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
from scipy.optimize import minimize

class NestedClusteredOptimization:
    def __init__(self, returns, method='max_sharpe', linkage_method='single'):
        self.returns = returns
        self.method = method
        self.linkage_method = linkage_method
        self.num_assets = returns.shape[1]
        self.weights = None
        
    def optimize(self):
        # Compute pairwise distance matrix and linkage matrix
        distance_matrix = np.sqrt(0.5 * (1 - np.corrcoef(self.returns, rowvar=False)))
        linkage_matrix = hierarchy.linkage(squareform(distance_matrix), method=self.linkage_method)
        
        # Traverse the hierarchical tree and compute cluster covariance matrices
        clusters = hierarchy.cut_tree(linkage_matrix, n_clusters=self.num_assets)
        cluster_covariances = {}
        for i in range(self.num_assets):
            if clusters[i][0] not in cluster_covariances:
                cluster_covariances[clusters[i][0]] = np.zeros((self.num_assets, self.num_assets))
            cluster_covariances[clusters[i][0]] += np.outer(self.returns[:,i], self.returns[:,i])
        for cluster in cluster_covariances:
            cluster_covariances[cluster] /= np.sum(clusters == cluster)
        
        # Compute nested covariance matrix and weight allocation
        nested_covariance_matrix = np.zeros((self.num_assets, self.num_assets))
        for i in range(self.num_assets):
            for j in range(self.num_assets):
                if clusters[i] == clusters[j]:
                    nested_covariance_matrix[i,j] = cluster_covariances[clusters[i]][i,j]
        if self.method == 'max_sharpe':
            def objective_function(weights):
                portfolio_return = np.dot(weights.T, self.returns.mean(axis=0))
                portfolio_variance = np.dot(weights.T, np.dot(nested_covariance_matrix, weights))
                return -(portfolio_return - 0.02) / np.sqrt(portfolio_variance)
        elif self.method == 'min_variance':
            def objective_function(weights):
                portfolio_variance = np.dot(weights.T, np.dot(nested_covariance_matrix, weights))
                return portfolio_variance
        
        constraint = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        bounds = [(0, None) for i in range(self.num_assets)]
        x0 = np.ones(self.num_assets) / self.num_assets
        result = minimize(objective_function, x0, method='SLSQP', constraints=constraint, bounds=bounds)
        
        if result.success:
            self.weights = result.x
        else:
            raise ValueError(result.message)
