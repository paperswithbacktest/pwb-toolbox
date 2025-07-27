from datetime import datetime
import datasets as ds
from pwb_toolbox.datasets import _get_hf_token
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats

from ..datasets import get_pricing


def _gibbs_sampler(price_changes, num_iterations=1000, burn_in=100):
    """
    Perform Gibbs sampling to estimate the parameters c and sigma^2_u.

    Parameters:
    price_changes (np.array): The array of price changes Δp_t.
    num_iterations (int): The number of Gibbs sampling iterations.
    burn_in (int): The number of initial iterations to discard.

    Returns:
    tuple: The posterior mean estimates of c and sigma^2_u.
    """
    # Initialize variables
    n = len(price_changes)
    c_samples = np.zeros(num_iterations)
    sigma_u_samples = np.zeros(num_iterations)
    q_t = np.sign(price_changes)

    # Initial values
    c = np.std(
        price_changes
    )  # Initialize c with the standard deviation of price changes
    sigma_u = np.var(
        price_changes
    )  # Initialize sigma^2_u with the variance of price changes

    # Gibbs Sampling
    for i in range(num_iterations):
        # Step 2: Update c and beta_m given sigma_u and q_t
        X = q_t[:, np.newaxis]
        y = price_changes
        beta_m = np.linalg.inv(X.T @ X) @ X.T @ y
        residuals = y - X @ beta_m
        c = np.sqrt(np.abs(np.cov(residuals[:-1], residuals[1:], bias=True)[0, 1]))

        # Step 3: Update sigma^2_u given c, beta_m, and q_t
        residuals = y - X @ beta_m
        sigma_u = np.var(residuals)

        # Step 4: Update q_t given c, beta_m, and sigma^2_u
        q_t = np.sign(np.random.normal(loc=c, scale=np.sqrt(sigma_u), size=n))

        # Store samples after burn-in
        if i >= burn_in:
            c_samples[i - burn_in] = c
            sigma_u_samples[i - burn_in] = sigma_u

    # Posterior mean estimates
    c_posterior = np.mean(c_samples[burn_in:])
    sigma_u_posterior = np.mean(sigma_u_samples[burn_in:])

    return c_posterior, sigma_u_posterior


def get_commissions(symbols, start_date="2020-01-01"):
    df = get_pricing(
        symbol_list=symbols,
        fields=["open", "high", "low", "close"],
        start_date=start_date,
        extend=True,
    )
    commissions = {}
    for symbol in df.columns.levels[0]:
        price_changes = np.log(df[symbol].close).diff().dropna().values
        c_estimate, _ = _gibbs_sampler(price_changes)
        commissions[symbol] = c_estimate / 10
    return commissions


if __name__ == "__main__":
    commissions = get_commissions(["AAPL", "MSFT", "GOOGL"])
    print(commissions)
