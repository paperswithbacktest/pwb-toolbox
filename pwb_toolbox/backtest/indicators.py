import backtrader as bt
import numpy as np


class SigmoidLongCompositeIndicator(bt.Indicator):
    """
    Returns a probabilistic 'long' score built from a weighted linear
    combination of several indicators, transformed by a sigmoid.

    Parameters
    ----------
    indicators : list[dict]
        Each dict must contain:
        - 'indicator_cls'    : an indicator class (e.g. bt.indicators.RSI)
        - 'indicator_kwargs' : kwargs for that indicator (may be empty {})
    weights : list[float]
        One weight per indicator.  Will be normalised by their sum.
    valueclip : float | None, optional
        Absolute clip applied before the sigmoid for numerical stability.
        Default is 10.  Set to None to disable.
    """

    lines = ("long",)
    params = dict(
        indicators=None,
        weights=None,
        bias=0.0,
        valueclip=10.0,
    )

    def __init__(self):
        if not self.p.indicators or not self.p.weights:
            raise ValueError("`indicators` and `weights` are both required")
        if len(self.p.indicators) != len(self.p.weights):
            raise ValueError("Length mismatch between `indicators` and `weights`")

        # Instantiate the child indicators
        self._inds = []
        for spec in self.p.indicators:
            indicator_cls = spec["indicator_cls"]
            indicator_kwargs = spec.get("indicator_kwargs", {})
            self._inds.append(indicator_cls(self.data, **indicator_kwargs))

        # Cache the (positive) weight normaliser
        self._w_sum = float(np.sum(self.p.weights))

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    # ---- main logic ------------------------------------------------------
    def next(self):
        # Weighted linear combination (scalar)
        z = sum(ind[0] * w for ind, w in zip(self._inds, self.p.weights)) + self.p.bias

        # Optional clipping to avoid overflow in exp()
        if self.p.valueclip is not None:
            clip = abs(self.p.valueclip)
            z = max(-clip, min(clip, z))

        # Sigmoid-scaled score in (0, 1)
        self.lines.long[0] = round(self._sigmoid(z))
