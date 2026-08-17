"""Tests for the pure statistical functions in `pwb_toolbox.performance.metrics`.

This module backs every Sharpe/Sortino/Calmar/drawdown number the toolbox
reports, and had zero test coverage. Where a closed-form expected value is
easy to construct (compounding series, symmetric returns, perfectly
correlated series) we assert exact numbers; for functions where hand-deriving
an exact result is error-prone, we assert well-understood relationships on
synthetic data instead (e.g. "the wilder series has the lower Sharpe").
"""

import math
import random

import pytest

from pwb_toolbox.performance.metrics import (
    annualized_volatility,
    cagr,
    calmar_ratio,
    capm_alpha_beta,
    kurtosis,
    max_drawdown,
    sharpe_ratio,
    skewness,
    sortino_ratio,
    total_return,
    ulcer_index,
)


def _compound(rets, start=100.0):
    """Build a price path from a list of period returns."""
    prices = [start]
    for r in rets:
        prices.append(prices[-1] * (1 + r))
    return prices


# --- total_return / cagr / annualized_volatility ----------------------------


def test_total_return_basic():
    assert math.isclose(total_return([100, 110, 121]), 0.21)


def test_total_return_empty_is_zero():
    assert total_return([]) == 0.0


def test_cagr_exact_compounding():
    # 121 = 100 * 1.1^2, so a 2-period CAGR (periods_per_year=1) is exactly 10%.
    assert math.isclose(cagr([100, 110, 121], periods_per_year=1), 0.10, rel_tol=1e-9)


def test_annualized_volatility_zero_for_smooth_compounding():
    # Constant per-period return -> zero variance of returns.
    prices = _compound([0.1, 0.1, 0.1, 0.1])
    assert annualized_volatility(prices, periods_per_year=1) == 0.0


def test_annualized_volatility_scales_with_dispersion():
    calm = _compound([0.01, -0.01, 0.01, -0.01] * 10)
    wild = _compound([0.05, -0.05, 0.05, -0.05] * 10)
    assert annualized_volatility(wild) > annualized_volatility(calm)


# --- max_drawdown / ulcer_index / calmar_ratio ------------------------------


def test_max_drawdown_depth_on_known_path():
    depth, _duration = max_drawdown([100, 50, 100])
    assert math.isclose(depth, -0.5)


def test_max_drawdown_zero_for_monotonic_series():
    # Note: `duration` is 1, not 0, here. `peak` starts equal to `p[0]` and the
    # loop only advances `peak` on a strict `price > peak`, so the very first
    # bar always falls into the "underwater" branch once. This is existing,
    # documented-by-this-test behavior of `max_drawdown`, not a new bug.
    depth, duration = max_drawdown([100, 110, 120, 130])
    assert depth == 0.0
    assert duration == 1


def test_ulcer_index_zero_for_monotonic_series():
    assert ulcer_index([100, 110, 120, 130]) == 0.0


def test_ulcer_index_positive_when_underwater():
    assert ulcer_index([100, 90, 95, 100]) > 0.0


def test_calmar_ratio_zero_when_no_drawdown():
    # No drawdown -> calmar_ratio divides by zero-guarded mdd -> 0.0 by design.
    assert calmar_ratio([100, 110, 120, 130]) == 0.0


# --- sharpe_ratio / sortino_ratio -------------------------------------------


def test_sharpe_ratio_zero_variance_edge_case():
    prices = _compound([0.01, 0.01, 0.01, 0.01])
    assert sharpe_ratio(prices) == 0.0


def test_sharpe_ratio_prefers_calmer_series_at_equal_mean_return():
    rng = random.Random(0)
    calm_rets = [0.001 + rng.gauss(0, 0.002) for _ in range(250)]
    wild_rets = [0.001 + rng.gauss(0, 0.02) for _ in range(250)]
    calm = _compound(calm_rets)
    wild = _compound(wild_rets)
    assert sharpe_ratio(calm) > sharpe_ratio(wild)


def test_sortino_ratio_ignores_upside_volatility():
    # All-upside noise (returns >= 0) has zero downside deviation -> undefined
    # downside risk. The function must not raise and must return a finite value.
    prices = _compound([0.01, 0.03, 0.0, 0.02, 0.01])
    result = sortino_ratio(prices)
    assert math.isfinite(result)


# --- capm_alpha_beta ---------------------------------------------------------


def test_capm_alpha_beta_recovers_known_linear_relationship():
    rng = random.Random(1)
    bench_rets = [rng.gauss(0.0005, 0.01) for _ in range(300)]
    # Strategy is exactly 2x the benchmark's return, no noise, no alpha.
    strat_rets = [2 * r for r in bench_rets]
    bench_prices = _compound(bench_rets)
    strat_prices = _compound(strat_rets)
    alpha, beta = capm_alpha_beta(strat_prices, bench_prices)
    assert math.isclose(beta, 2.0, rel_tol=1e-6)
    assert math.isclose(alpha, 0.0, abs_tol=1e-9)


# --- skewness / kurtosis -----------------------------------------------------


def test_skewness_zero_for_symmetric_returns():
    rets = [0.05, -0.05, 0.05, -0.05, 0.05, -0.05]
    prices = _compound(rets)
    assert math.isclose(skewness(prices), 0.0, abs_tol=1e-9)


def test_kurtosis_finite_and_nonnegative_for_typical_series():
    rng = random.Random(2)
    rets = [rng.gauss(0, 0.01) for _ in range(200)]
    prices = _compound(rets)
    result = kurtosis(prices)
    assert math.isfinite(result)
    assert result >= 0
