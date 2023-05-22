from numba import jit
import numpy as np


def bayesian_slope(x) -> float:
    """
    Bayesian slope: (S(12)-S(1)) / S(1)
    """
    if len(x) < 12:
        return np.NaN
    else:
        return (x[-1] - x[0]) / 12 / np.median(x)


def linear_regression_slope(x) -> float:
    """
    Slope of the linear regression: slope(close(1), ..., close(12))
    """
    if len(x) < 12:
        return np.NaN
    else:
        return np.polyfit(range(12), x, 1)[0] / np.median(x)


def median_of_local_slopes(x) -> float:
    """
    Median of local slopes: median(close(12)-close(11), close(11)-close(10), ..., close(2)-close(1))
    """
    if len(x) < 12:
        return np.NaN
    else:
        return np.median(np.diff(x)) / np.median(x)


def median_of_progressive_slopes(x) -> float:
    """
    Median of progressive slopes: median(close(2)-close(1), (close(3)-close(1)) / 2, ..., (close(12)-close(1)) / 11)
    """
    if len(x) < 12:
        return np.NaN
    else:
        return np.median((x[1:] - x[0]) / np.arange(1, 12)) / np.median(x)


@jit(nopython=True)
def barycentre_of_progressive_slopes(x) -> float:
    """
    Barycentre of progressive slopes: sum(volume(n)*(close(n)-close(1)/n)/sum(volume(n))
    """
    if len(x) < 12:
        return np.NaN
    else:
        returns = (x[1:, 0] - x[0, 0]) / np.arange(1, 12) / np.median(x[:, 0])
        volumes = x[1:, 1]
        return np.sum(returns / volumes) / np.sum(1 / volumes)
