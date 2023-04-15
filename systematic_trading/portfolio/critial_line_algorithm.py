import numpy as np
from scipy.optimize import minimize


class CriticalLineAlgorithm:
    def __init__(self, returns, lower_bounds=None, upper_bounds=None):
        self.returns = returns
        self.num_assets = returns.shape[1]
        self.lower_bounds = lower_bounds if lower_bounds else np.zeros(self.num_assets)
        self.upper_bounds = upper_bounds if upper_bounds else np.ones(self.num_assets)
        self.weights = None

    def optimize(self, target_return):
        # Objective function to minimize
        def objective_function(weights):
            portfolio_return = np.sum(weights * self.returns.mean(axis=0))
            portfolio_variance = np.dot(weights.T, np.dot(self.returns.cov(), weights))
            return portfolio_variance

        # Constraints on weights
        constraints = [
            {"type": "ineq", "fun": lambda x: self.lower_bounds - x},
            {"type": "ineq", "fun": lambda x: x - self.upper_bounds},
        ]

        # Constraint for target return
        def target_return_constraint(weights):
            return np.sum(weights * self.returns.mean(axis=0)) - target_return

        constraints.append({"type": "eq", "fun": target_return_constraint})

        # Initial guess for weights
        x0 = np.ones(self.num_assets) / self.num_assets

        # Optimisation
        result = minimize(
            objective_function, x0, method="SLSQP", constraints=constraints
        )

        if result.success:
            self.weights = result.x
        else:
            raise ValueError(result.message)
