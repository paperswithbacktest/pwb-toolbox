from datetime import datetime
import datasets as ds
from pwb_toolbox.datasets import _get_hf_token
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats

from ..datasets import get_pricing


_MIN_OBS = 5  # need at least this many returns to attempt Gibbs
_EPS = 1e-12  # numeric floor to avoid divide-by-zero


def _roll_c(price_changes: np.ndarray) -> float:
    """Safe Roll(1984)-style spread proxy from lag-1 autocov of Δp."""
    pc = np.asarray(price_changes, dtype=float)
    pc = pc[np.isfinite(pc)]
    n = pc.size
    if n < 3:
        return 0.0
    pc0 = pc[:-1]
    pc1 = pc[1:]
    # manual covariance (avoids np.cov ddof warnings on short arrays)
    m0 = pc0.mean()
    m1 = pc1.mean()
    cov1 = ((pc1 - m1) * (pc0 - m0)).mean()
    # Roll: c = sqrt(max(0, -γ1))
    return float(np.sqrt(max(0.0, -cov1)))


def _gibbs_sampler(price_changes, num_iterations=1000, burn_in=200):
    """
    Robust Gibbs sampler for c and sigma^2_u with defensive guards.
    Falls back to a Roll-style estimator on short series.
    """
    pc = np.asarray(price_changes, dtype=float)
    pc = pc[np.isfinite(pc)]
    n = pc.size

    # Fallback for short/empty input
    if n < _MIN_OBS:
        c_fallback = _roll_c(pc)
        return float(c_fallback), 0.0

    # Allocate only for post-burn-in samples (no slicing bugs later)
    n_keep = max(1, num_iterations - burn_in)
    c_samples = np.empty(n_keep, dtype=float)
    sigma_u_samples = np.empty(n_keep, dtype=float)

    # Initial state
    q_t = np.sign(pc)
    q_t[q_t == 0] = 1.0
    c = np.std(pc) if n > 1 else 0.0
    c = float(max(c, _EPS))
    sigma_u = np.var(pc, ddof=1) if n > 1 else 1.0
    sigma_u = float(max(sigma_u, _EPS))

    keep_idx = 0
    for i in range(num_iterations):
        # --- Update beta_m given sigma_u and q_t (1 regressor) ---
        X = q_t.reshape(-1, 1)  # (n,1)
        y = pc  # (n,)
        # least-squares that never throws on rank-deficiency
        beta_m, *_ = np.linalg.lstsq(X, y, rcond=None)

        # --- Residuals ---
        resid = y - X.dot(beta_m)
        rlen = resid.size

        # --- Update c from lag-1 covariance of residuals (safe) ---
        if rlen >= 3:
            r0 = resid[:-1]
            r1 = resid[1:]
            m0 = r0.mean()
            m1 = r1.mean()
            cov1 = ((r1 - m1) * (r0 - m0)).mean()
            c = float(np.sqrt(max(_EPS, -cov1)))  # Roll logic on residuals
        else:
            c = float(max(_EPS, np.std(resid) if rlen > 1 else c))

        # --- Update sigma^2_u ---
        if rlen >= 2:
            sigma_u = float(max(_EPS, np.var(resid, ddof=1)))
        else:
            sigma_u = float(max(_EPS, sigma_u))

        # --- Update q_t ---
        draws = np.random.normal(loc=c, scale=np.sqrt(max(_EPS, sigma_u)), size=n)
        q_t = np.sign(draws)
        q_t[q_t == 0] = 1.0

        # Store after burn-in
        if i >= burn_in and keep_idx < n_keep:
            c_samples[keep_idx] = c
            sigma_u_samples[keep_idx] = sigma_u
            keep_idx += 1

    # Posterior means (no extra slicing)
    c_posterior = float(np.mean(c_samples))
    sigma_u_posterior = float(np.mean(sigma_u_samples))
    return c_posterior, sigma_u_posterior


def get_commissions(symbols, start_date="2020-01-01"):
    df = get_pricing(
        symbol_list=symbols,
        fields=["open", "high", "low", "close"],
        start_date=start_date,
        extend=True,
    )

    commissions = {}
    if df is None or df.empty:
        # Conservative fallback if nothing loaded
        return {s: 1e-4 for s in symbols}

    # Work only with symbols that actually came back
    try:
        available = set(df.columns.get_level_values(0))
    except Exception:
        # if columns aren't MultiIndex for some reason
        available = set(df.columns)

    c_pool = []

    for s in symbols:
        if s not in available:
            commissions[s] = None
            continue

        close = (
            pd.to_numeric(df[s].close, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        if close.size < _MIN_OBS + 1:
            commissions[s] = None
            continue

        price_changes = np.diff(np.log(close.values))  # Δp_t
        if price_changes.size < _MIN_OBS:
            commissions[s] = None
            continue

        c_est, _ = _gibbs_sampler(price_changes)
        if np.isfinite(c_est):
            commissions[s] = float(c_est) / 10.0
            c_pool.append(float(c_est))
        else:
            commissions[s] = None

    # Fill missing with median of successful estimates (or a small default)
    if c_pool:
        default_c = float(np.median(c_pool)) / 10.0
    else:
        default_c = 1e-4

    for s in symbols:
        if commissions.get(s) is None:
            commissions[s] = default_c

    return commissions


if __name__ == "__main__":
    commissions = get_commissions(["AAPL", "MSFT", "GOOGL"])
    print(commissions)
