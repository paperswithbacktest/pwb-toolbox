import numpy as np

class TheoryImpliedCorrelation:
    def __init__(self, corr, assets, sectors=None):
        self.corr = corr
        self.assets = assets
        self.sectors = sectors
        self.num_assets = corr.shape[0]
        self.num_sectors = len(set(sectors)) if sectors is not None else 0

    def _get_sector_indices(self):
        sector_indices = {}
        for i in range(self.num_sectors):
            sector_indices[i] = [j for j in range(self.num_assets) if self.sectors[j] == i]
        return sector_indices

    def _get_theory_corr(self):
        theory_corr = np.zeros_like(self.corr)
        if self.sectors is None:
            return self.corr
        sector_indices = self._get_sector_indices()
        for i in range(self.num_sectors):
            for j in range(i+1):
                if i == j:
                    indices = sector_indices[i]
                    theory_corr[np.ix_(indices, indices)] = np.identity(len(indices))
                else:
                    indices_i = sector_indices[i]
                    indices_j = sector_indices[j]
                    mean_i = np.mean(self.corr[np.ix_(indices_i, indices_i)])
                    mean_j = np.mean(self.corr[np.ix_(indices_j, indices_j)])
                    theory_corr[np.ix_(indices_i, indices_j)] = mean_i * mean_j
                    theory_corr[np.ix_(indices_j, indices_i)] = mean_i * mean_j
        return theory_corr

    def get_implied_cov(self):
        theory_corr = self._get_theory_corr()
        diag = np.diag(np.diag(self.corr))
        inv_sqrt_diag = np.linalg.inv(sqrtm(diag))
        implied_corr = np.dot(np.dot(inv_sqrt_diag, theory_corr), inv_sqrt_diag)
        implied_cov = np.diag(np.diag(self.corr)) * implied_corr
        return implied_cov

    def get_implied_corr(self):
        theory_corr = self._get_theory_corr()
        diag = np.diag(np.diag(self.corr))
        inv_sqrt_diag = np.linalg.inv(sqrtm(diag))
        implied_corr = np.dot(np.dot(inv_sqrt_diag, theory_corr), inv_sqrt_diag)
        return implied_corr
