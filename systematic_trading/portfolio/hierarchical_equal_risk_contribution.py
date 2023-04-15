import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist

class HierarchicalEqualRiskContribution:
    def __init__(self, returns, linkage_method='ward', alpha=2):
        self.returns = returns
        self.linkage_method = linkage_method
        self.alpha = alpha
        self.num_assets = returns.shape[1]
        self.clusters = None
        self.weights = None
        
    def fit(self):
        # Compute pairwise distances
        dists = pdist(self.returns)
        
        # Perform hierarchical clustering
        self.clusters = linkage(dists, method=self.linkage_method)
        
        # Assign assets to clusters
        max_num_clusters = int(np.ceil(np.sqrt(self.num_assets)))
        self.clusters = fcluster(self.clusters, max_num_clusters, criterion='maxclust')
        
        # Compute cluster risk contributions
        cluster_variances = np.zeros(max_num_clusters)
        for i in range(max_num_clusters):
            cluster_variances[i] = self._compute_cluster_variance(i+1)
        
        # Compute weights
        self.weights = self._compute_weights(cluster_variances, max_num_clusters)
    
    def _compute_cluster_variance(self, cluster_num):
        idx = np.where(self.clusters == cluster_num)[0]
        if len(idx) == 1:
            return 0
        else:
            cov = np.cov(self.returns[:, idx], rowvar=False)
            return np.dot(np.ones(len(idx)), np.dot(cov, np.ones(len(idx)))) / len(idx)
    
    def _compute_weights(self, cluster_variances, max_num_clusters):
        # Initialize weights
        weights = np.zeros(self.num_assets)
        queue = [(self.clusters.max()+1, np.arange(self.num_assets))]
        
        # Breadth-first search to compute weights
        while queue:
            cluster_num, idx = queue.pop(0)
            if len(idx) == 1:
                weights[idx[0]] = 1
            else:
                cov = np.cov(self.returns[:, idx], rowvar=False)
                dists = pdist(cov)
                subclusters = fcluster(linkage(dists, method='ward'), 2, criterion='maxclust')
                subcluster_variances = np.zeros(2)
                for i in range(2):
                    subcluster_variances[i] = np.dot(np.ones(len(idx)), np.dot(cov[subclusters == i+1][:, subclusters == i+1], np.ones(len(idx[subclusters == i+1]))))
                if self.alpha == 2:
                    subcluster_weights = 1 / (2 * np.sqrt(subcluster_variances))
                else:
                    subcluster_weights = np.power(subcluster_variances, 1-self.alpha/2)
                    subcluster_weights /= np.sum(subcluster_weights)
                for i in range(2):
                    subidx = idx[subclusters == i+1]
                    if len(subidx) == 1:
                        weights[subidx[0]] = 1
                    else:
                        queue.append((cluster_num+1, subidx))
                weights[idx] = subcluster_weights.dot(np.ones(len(idx)))
        
        # Normalize weights
        weights /= np.sum(weights)
        
        return weights
