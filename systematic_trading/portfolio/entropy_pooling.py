import numpy as np


class EntropyPooling:
    def __init__(self, cov, prior, views, scale=1.0, gamma=1.0):
        self.cov = cov
        self.prior = prior
        self.views = views
        self.scale = scale
        self.gamma = gamma
        self.num_assets = cov.shape[0]
        self.num_views = views.shape[0]
        self.ent_weight = np.ones(self.num_assets) / self.num_assets

    def _get_ent_weight(self, mu):
        cov = self.cov + self.gamma * np.identity(self.num_assets)
        inv_cov = np.linalg.inv(cov)
        prior_var = np.dot(np.dot(self.prior, cov), self.prior)
        view_var = np.sum(
            [self.scale * np.dot(np.dot(v[1], cov), v[1]) for v in self.views]
        )
        obj_func = lambda w: -np.dot(w, np.log(w))
        eq_cons = {"type": "eq", "fun": lambda w: np.dot(w, mu) - 1.0}
        ineq_cons = {
            "type": "ineq",
            "fun": lambda w: np.dot(np.dot(w, cov), w) - prior_var - view_var,
        }
        bounds = [(0, 1) for i in range(self.num_assets)]
        res = minimize(
            obj_func,
            self.ent_weight,
            method="SLSQP",
            constraints=[eq_cons, ineq_cons],
            bounds=bounds,
        )
        self.ent_weight = res.x
        return self.ent_weight

    def get_posterior(self):
        view_mu = np.array([v[0] for v in self.views])
        view_cov = np.array([v[1] for v in self.views])
        ent_weight = self._get_ent_weight(view_mu)
        posterior_cov = self.cov + self.gamma * np.identity(self.num_assets)
        for i in range(self.num_views):
            view_diff = self.scale * np.dot(
                posterior_cov, np.dot(view_cov[i], posterior_cov)
            )
            posterior_cov += view_diff
        posterior_mean = np.dot(ent_weight, view_mu)
        return posterior_mean, posterior_cov
