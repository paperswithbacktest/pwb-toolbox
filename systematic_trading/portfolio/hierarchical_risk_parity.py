import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, dendrogram


class HierarchicalRiskParity:
    def __init__(self, returns, linkage_method="ward"):
        self.returns = returns
        self.linkage_method = linkage_method
        self.clusters = None
        self.weights = None

    def _get_cluster_var(self, cvar):
        cluster_var = np.dot(cvar.T, self.weights)
        return cluster_var

    def _get_quasi_diag(self, linkage_matrix):
        link = linkage_matrix.copy()
        sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
        num_items = link[-1, 3]
        while sort_ix.max() >= num_items:
            idx = sort_ix[sort_ix >= num_items].index
            sort_ix[idx] = link[int(idx), :2]
            sort_ix = pd.Series(sort_ix).sort_values()
        return sort_ix.tolist()

    def _get_rec_bipart(self, sort_ix, cvar):
        w = pd.Series(1, index=sort_ix)
        c_items = [sort_ix]
        while len(c_items) > 0:
            c_items = [
                i[j:k]
                for i in c_items
                for j, k in ((0, len(i) // 2), (len(i) // 2, len(i)))
                if len(i) > 1
            ]
            for i in range(0, len(c_items), 2):
                c1 = c_items[i]
                c2 = c_items[i + 1]
                var_c1 = self._get_cluster_var(cvar[c1])
                var_c2 = self._get_cluster_var(cvar[c2])
                w[c1] *= var_c2 / (var_c1 + var_c2)
                w[c2] *= var_c1 / (var_c1 + var_c2)
        return w.sort_index()

    def fit(self):
        cov = self.returns.cov().values
        corr = self.returns.corr().values
        dist = np.sqrt(0.5 * (1 - corr))
        link = linkage(dist, self.linkage_method)
        sort_ix = self._get_quasi_diag(link)
        cvar = np.diag(cov)
        weights = self._get_rec_bipart(sort_ix, cvar)
        self.clusters = sort_ix
        self.weights = weights.values.reshape(-1, 1)

    def get_weights(self):
        return self.weights

    def get_clusters(self):
        return self.clusters

    def plot_dendrogram(self):
        dist = np.sqrt(0.5 * (1 - self.returns.corr()))
        link = linkage(dist, self.linkage_method)
        dendrogram(link, labels=self.returns.columns.tolist(), leaf_rotation=90)
