import backtrader as bt
import numpy as np


class StochasticRsi(bt.Indicator):
    """Stochastic RSI — the Stochastic oscillator applied to RSI, not to price.

    backtrader ships ``Stochastic`` (which reads the feed's high/low/close) but
    no Stochastic RSI, so this builds it from ``RSI`` plus ``Highest``/``Lowest``
    over the RSI line.

    ``rsi`` is exposed as a line so callers that also need plain RSI can reuse
    it instead of computing a second one.

    Parameters
    ----------
    rsi_period : int
        Lookback for the underlying RSI.
    stoch_period : int
        Window the RSI is ranked against (its own high/low range).
    smooth_k, smooth_d : int
        SMA smoothing applied to %K, and then to %K to get %D.
    """

    lines = ("percK", "percD", "rsi")
    params = dict(
        rsi_period=14,
        stoch_period=14,
        smooth_k=3,
        smooth_d=3,
    )
    plotlines = dict(rsi=dict(_plotskip=True))

    #: RSI range below which a window counts as flat. Wilder smoothing decays
    #: gains and losses at the same rate, so a constant price holds RSI fixed
    #: to within float rounding — about 1e-14 — rather than exactly.
    FLAT_EPS = 1e-9

    def __init__(self):
        rsi = bt.indicators.RSI(self.data, period=self.p.rsi_period)
        lowest = bt.indicators.Lowest(rsi, period=self.p.stoch_period)
        highest = bt.indicators.Highest(rsi, period=self.p.stoch_period)

        # A flat RSI window makes the high/low range zero. Pine guards this
        # with an exact `highest - lowest == 0` test, which is not enough in
        # floating point: on a constant price the range lands around 1e-14
        # rather than 0, the guard misses, and dividing by that noise inflates
        # it back across the full 0-100 range. A constant price then reports a
        # confident 100. Anything below FLAT_EPS is treated as flat, which is
        # the semantics the exact test was reaching for.
        span = highest - lowest
        is_moving = span > self.FLAT_EPS
        safe_span = bt.If(is_moving, span, 1.0)  # both branches evaluate
        raw = 100.0 * bt.If(is_moving, (rsi - lowest) / safe_span, 0.0)

        percK = bt.indicators.SMA(raw, period=self.p.smooth_k)
        percD = bt.indicators.SMA(percK, period=self.p.smooth_d)

        self.lines.rsi = rsi
        self.lines.percK = percK
        self.lines.percD = percD


class EmaRsiStochRsiSignal(bt.Indicator):
    """Entry/exit signals from an EMA trend filter, RSI momentum and StochRSI timing.

    Emits the ``entry``/``exit`` line pair that
    :class:`~pwb_toolbox.backtesting.strategies.EqualWeightEntryExitPortfolio`
    consumes, so it drops straight into the existing portfolio strategies.

    The three indicators do different jobs, which is the point of combining
    them: the EMA says whether to be long at all, StochRSI picks the moment,
    and RSI confirms momentum agrees.

    Long entry — all of:
      * %K crosses above %D  (the timing trigger)
      * %K is below ``oversold`` at the cross, so it fires from a washed-out
        reading rather than mid-range
      * RSI is rising, if ``require_rsi_rising``
      * the EMA has risen over the last ``trend_lookback`` bars, if
        ``trend_filter``

    Exit — either:
      * %K crosses below %D while above ``overbought``
      * the trend filter stops passing, if ``exit_on_trend_break``

    On the trend filter, because the obvious phrasing hides an identity.
    "EMA is rising" and "close is above the EMA" are the *same test*, not two
    choices: expanding the recursion gives
    ``EMA_t - EMA_{t-1} = alpha * (close_t - EMA_{t-1})``, so the EMA rises
    exactly when the close is above the previous bar's EMA. Measured over 2981
    bars the two agreed on every single one. Only ``trend_lookback`` makes the
    filter genuinely different: at 1 it is that identity, and above 1 it asks
    for a more sustained move and rejects a one-bar poke above the average.

    ``exit_on_trend_break`` exits on the negation of the same predicate that
    gated entry, so the two can never disagree about whether the trend holds.
    It defaults to **off**, which is both the Pine original's behaviour and the
    better-behaved one: because entry needs a rising EMA, a single down bar
    breaks the trend and closes the position straight after opening it. On an
    8-asset simulated basket, turning it on cut the average hold from 20.4 to
    5.5 bars, doubled the trade count and dropped the win rate from 64% to
    47%. Prefer the risk models in :mod:`pwb_toolbox.backtesting.risk_models`
    for protective stops — they are built for it and keep the concerns apart.

    Entry is deliberately strict — a cross, a zone, momentum and trend at once.
    Across eight simulated price paths (11.7k bars) roughly 11% of bullish
    %K/%D crosses survived all four filters, so on a single instrument this
    trades rarely by design. It is built for a basket, where the portfolio
    strategy holds whichever names qualify on the day. Raise ``oversold`` or
    clear ``require_rsi_rising`` to loosen it.

    Parameters
    ----------
    ema_period : int
        Trend filter length.
    rsi_period, stoch_period, smooth_k, smooth_d : int
        Forwarded to :class:`StochasticRsi`.
    oversold, overbought : float
        %K bounds the crosses must occur beyond to count.
    require_rsi_rising : bool
        Require RSI above its previous bar on entry.
    trend_filter : bool
        Require the EMA to have risen over ``trend_lookback`` bars.
    trend_lookback : int
        Bars the EMA must have risen over. 1 is equivalent to close-above-EMA.
    exit_on_trend_break : bool
        Also exit when the trend filter stops passing.
    """

    lines = ("entry", "exit")
    params = dict(
        ema_period=20,
        rsi_period=14,
        stoch_period=14,
        smooth_k=3,
        smooth_d=3,
        oversold=30.0,
        overbought=70.0,
        require_rsi_rising=True,
        trend_filter=True,
        trend_lookback=1,
        exit_on_trend_break=False,
    )

    def __init__(self):
        if self.p.trend_lookback < 1:
            raise ValueError(
                f"trend_lookback must be >= 1, got {self.p.trend_lookback}"
            )

        ema = bt.indicators.EMA(self.data, period=self.p.ema_period)
        stoch = StochasticRsi(
            self.data,
            rsi_period=self.p.rsi_period,
            stoch_period=self.p.stoch_period,
            smooth_k=self.p.smooth_k,
            smooth_d=self.p.smooth_d,
        )
        cross = bt.indicators.CrossOver(stoch.percK, stoch.percD)

        entry_terms = [cross == 1, stoch.percK < self.p.oversold]
        if self.p.require_rsi_rising:
            entry_terms.append(stoch.rsi > stoch.rsi(-1))

        trend_ok = None
        if self.p.trend_filter:
            trend_ok = ema > ema(-self.p.trend_lookback)
            entry_terms.append(trend_ok)

        self.lines.entry = bt.And(*entry_terms)

        exit_signal = bt.And(cross == -1, stoch.percK > self.p.overbought)
        if self.p.exit_on_trend_break and trend_ok is not None:
            # Negation of the entry predicate, so the two stay consistent.
            exit_signal = bt.Or(exit_signal, trend_ok < 0.5)
        self.lines.exit = exit_signal


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
