import numpy as np

from ..engine import load as _load_engine

bt = _load_engine()  # backtrader by default, Tradewind on request; see pwb_toolbox.engine


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


def _momentum_score(lookback: int, skip: int):
    """``close[-skip] / close[-lookback] - 1``: the 12-1 momentum with the defaults."""

    def score(data):
        start = float(data.close[-lookback])
        end = float(data.close[-skip]) if skip else float(data.close[0])
        if not (np.isfinite(start) and np.isfinite(end)) or start <= 0:
            return np.nan
        return end / start - 1.0

    return score


def _as_quantiles(value, default):
    if value is None:
        return frozenset(default)
    if isinstance(value, (int, np.integer)):
        return frozenset((int(value),))
    return frozenset(int(v) for v in value)


class CrossSectionalQuantileSignal(bt.Indicator):
    """+1 / -1 / 0 for one name, from its quantile in a ranking of a whole universe.

    Built for ``MonthlyLongShortQuantilePortfolio``, which creates one per feed
    as ``indicator_cls(d, universe=self.datas, **indicator_kwargs)`` and reads
    ``self.sig[d._name][0]``::

        run_strategy(
            indicator_cls=CrossSectionalQuantileSignal,
            indicator_kwargs={"lookback": 252, "skip": 21, "quantiles": 10},
            strategy_cls=MonthlyLongShortQuantilePortfolio,
            strategy_kwargs={"leverage": 0.9},
            symbols=["sp500"], ..., short_borrow_bps=50,
        )

    (the full example: ``python -m pwb_toolbox.docs backtesting``, section
    "Long-short by quantiles").

    Contract
    --------
    On each bar, every eligible name of ``universe`` is scored, the scores are
    sorted (ties by feed name) and cut into ``quantiles`` groups of equal
    count, 0 the lowest: the name at rank ``i`` of ``n`` is in quantile
    ``i * quantiles // n``. The line ``signal`` is ``+1`` for a name in
    ``long_q`` (default: the highest quantile), ``-1`` in ``short_q``
    (default: the lowest), ``0`` otherwise, for an ineligible name, and on
    every bar where fewer than ``min_names`` names (default ``quantiles``)
    could be scored.

    The score is the 12-1 momentum by default: ``close[-skip] / close[-lookback] - 1``
    (``lookback=252``, ``skip=21``), defined once a feed has more than
    ``lookback`` bars. ``score`` replaces it: a callable taking a feed and
    returning a float (NaN excludes the name), called with the feed on the
    current bar; it must read only ``[0]`` and negative indices.

    A name is eligible when the strategy that owns the indicator says it is
    a member (``is_member``, which ``run_strategy`` answers ``False`` for a
    name outside a point-in-time universe on that bar) and tradable
    (``is_tradable``: ``BaseStrategy``'s answers ``False`` on a flat line).
    Without such an owner (a plain ``bt.Strategy``), a name whose last three
    closes are equal is taken for a flat line and skipped.

    The ranking is computed once per bar for the whole universe and shared by
    every indicator built on the same universe and parameters (a cache on the
    owning strategy, keyed by the bar's date), not once per name: on 1 500
    names that is 1 500 scores a bar instead of 2.25 million.

    Engines
    -------
    The indicator reads the feeds of the other names in ``next``. backtrader's
    vectorised mode (``runonce=True``, its default) computes each indicator
    over the whole history before the strategy runs, advancing only that
    indicator's own feed, so the other feeds would be read at the wrong bar:
    the class sets ``_nextforce = True``, which makes backtrader run the whole
    Cerebro bar by bar (slower, exact). Tradewind steps an indicator that
    defines only ``next`` with the strategy, and its owner is
    ``_tw_strategy``.

    Limits
    ------
    * With ``["sp500"]`` and ``pit_exit="hold"`` (the default) the feed of a
      name is flat while it is outside the universe. A name that has just
      entered is a member, so it is ranked, but the start of its window may
      fall in the flat segment, i.e. on its last member close before an
      absence or on the back-filled first price: its momentum is measured
      from that price, not from a real one. Names listed after the start
      are flat before their first bar for the same reason; while that flat
      stretch includes the current bar they are not tradable and skipped.
    * The quantiles are of count, not of value; with ``n`` not a multiple of
      ``quantiles`` the groups differ by one name.
    * ``MonthlyLongShortQuantilePortfolio`` rebalances from a timer that fires
      before the indicators of the bar are computed: on the first session of
      a month it reads the ranking of the previous session's close.
    """

    lines = ("signal",)
    params = dict(
        universe=None,
        lookback=252,
        skip=21,
        quantiles=10,
        long_q=None,
        short_q=None,
        score=None,
        min_names=None,
    )
    # backtrader: run the Cerebro bar by bar, see "Engines" above.
    _nextforce = True

    def __init__(self):
        p = self.p
        if p.quantiles < 2:
            raise ValueError(f"quantiles={p.quantiles}: at least 2")
        if not 0 <= p.skip < p.lookback:
            raise ValueError(f"skip={p.skip}, lookback={p.lookback}: 0 <= skip < lookback")
        self._universe = list(p.universe) if p.universe is not None else [self.data]
        self._long = _as_quantiles(p.long_q, (p.quantiles - 1,))
        self._short = _as_quantiles(p.short_q, (0,))
        bad = [q for q in self._long | self._short if not 0 <= q < p.quantiles]
        if bad:
            raise ValueError(f"long_q/short_q {sorted(bad)}: quantiles are 0..{p.quantiles - 1}")
        if self._long & self._short:
            raise ValueError(f"quantiles {sorted(self._long & self._short)} both long and short")
        self._min_names = max(int(p.min_names if p.min_names is not None else p.quantiles), 1)
        self._score = p.score if p.score is not None else _momentum_score(p.lookback, p.skip)
        self._key = (
            tuple(id(d) for d in self._universe), p.lookback, p.skip, p.quantiles,
            self._long, self._short, self._min_names, id(self._score) if p.score else None,
        )

    # -- the strategy that owns it --------------------------------------------
    def _strategy(self):
        owner = getattr(self, "_tw_strategy", None)  # Tradewind
        if owner is not None:
            return owner
        owner = getattr(self, "_owner", None)  # backtrader: the strategy, or a parent indicator
        while owner is not None and not isinstance(owner, bt.Strategy):
            owner = getattr(owner, "_owner", None)
        return owner

    def _cache(self):
        owner = self._strategy()
        holder = owner if owner is not None else self._universe[0]
        caches = getattr(holder, "_pwb_xsq_cache", None)
        if caches is None:
            caches = {}
            setattr(holder, "_pwb_xsq_cache", caches)
        return owner, caches.setdefault(self._key, {"bar": None, "signals": {}, "rankings": 0})

    @staticmethod
    def _flat(data) -> bool:
        if len(data) < 3:
            return True
        return data.close[0] == data.close[-1] == data.close[-2]

    def _rank(self, owner) -> dict:
        is_member = getattr(owner, "is_member", None)
        is_tradable = getattr(owner, "is_tradable", None)
        scored = []
        for d in self._universe:
            if len(d) <= self.p.lookback:
                continue
            if is_member is not None and not is_member(d):
                continue
            if is_tradable is not None:
                if not is_tradable(d):
                    continue
            elif self._flat(d):
                continue
            value = self._score(d)
            if value is None or not np.isfinite(value):
                continue
            scored.append((float(value), str(getattr(d, "_name", "")), id(d)))
        n = len(scored)
        if n < self._min_names:
            return {}
        scored.sort()
        q = self.p.quantiles
        signals = {}
        for i, (_, _, key) in enumerate(scored):
            bucket = i * q // n
            if bucket in self._long:
                signals[key] = 1
            elif bucket in self._short:
                signals[key] = -1
        return signals

    def next(self):
        owner, cache = self._cache()
        bar = (len(self.data), float(self.data.datetime[0]))
        if cache["bar"] != bar:
            cache["signals"] = self._rank(owner)
            cache["bar"] = bar
            cache["rankings"] += 1
        self.lines.signal[0] = cache["signals"].get(id(self.data), 0)

    def prenext(self):
        self.lines.signal[0] = 0
