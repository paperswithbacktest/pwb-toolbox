import numpy as np
from scipy.linalg import eigvals, eigvalsh, sqrtm
from sklearn.cluster import SpectralClustering

class DenoisingDetoning:
    def __init__(self, cov):
        self.cov = cov
        self.num_assets = cov.shape[0]

    def constant_residual_eigenvalue_method(self, target=None):
        eigenvalues, eigenvectors = eigvalsh(self.cov)
        if target is None:
            target = np.median(eigenvalues)
        mask = eigenvalues > target
        eigenvalues[mask] = target
        diagonal_matrix = np.diag(eigenvalues)
        denoised_cov = np.dot(np.dot(eigenvectors, diagonal_matrix), np.linalg.inv(eigenvectors))
        return denoised_cov

    def spectral_clustering_filter_method(self, num_clusters=None):
        if num_clusters is None:
            num_clusters = int(np.sqrt(self.num_assets))
        sc = SpectralClustering(n_clusters=num_clusters, affinity='precomputed', assign_labels='discretize')
        similarity_matrix = np.exp(-self.cov ** 2 / 2)
        labels = sc.fit_predict(similarity_matrix)
        filtered_similarity_matrix = np.zeros_like(similarity_matrix)
        for i in range(num_clusters):
            for j in range(num_clusters):
                if i == j:
                    continue
                mask = np.logical_and(labels == i, labels == j)
                filtered_similarity_matrix[mask] = similarity_matrix[mask]
        filtered_cov = -np.log(filtered_similarity_matrix)
        denoised_cov = self.cov * filtered_cov / np.diag(filtered_cov).reshape(-1, 1)
        return denoised_cov

    def targeted_shrinkage(self, delta):
        eigenvalues, eigenvectors = eigvalsh(self.cov)
        diagonal_matrix = np.diag(eigenvalues)
        targeted_diagonal_matrix = delta * diagonal_matrix

        denoised_cov = np.dot(np.dot(eigenvectors, targeted_diagonal_matrix), np.linalg.inv(eigenvectors))
        return denoised_cov

    def get_denoised_cov(self, method='crem', delta=None, num_clusters=None):
        if method == 'crem':
            return self.constant_residual_eigenvalue_method(delta)
        elif method == 'scfm':
            return self.spectral_clustering_filter_method(num_clusters)
        elif method == 'targeted':
            return self.targeted_shrinkage(delta)
        else:
            raise ValueError("Invalid denoising method. Choose from 'crem', 'scfm', or 'targeted'.")
