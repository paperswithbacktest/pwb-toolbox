"""Tests for `StochasticRsi` and `EmaRsiStochRsiSignal`.

backtrader has no Stochastic RSI, so the oscillator here is hand-built and the
first job of these tests is to prove the arithmetic against an independent
pandas implementation rather than against itself. Everything is synthetic and
offline — no feed download, no broker.
"""

import numpy as np
import pandas as pd
import pytest

import backtrader as bt

from pwb_toolbox.backtesting.indicators import EmaRsiStochRsiSignal, StochasticRsi
from pwb_toolbox.backtesting.strategies import EqualWeightEntryExitPortfolio

# --------------------------------------------------------------------------
# fixtures and helpers
# --------------------------------------------------------------------------


def make_frame(close):
    """An OHLCV frame around a close series, on business days."""
    close = np.asarray(close, dtype=float)
    index = pd.bdate_range("2020-01-01", periods=len(close))
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.full(len(close), 1e6),
        },
        index=index,
    )


def gbm(seed, n=600, mu=0.08, sigma=0.18):
    """A geometric-Brownian price path — no cycle for an oscillator to lock onto."""
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    steps = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
    return 100.0 * np.exp(np.cumsum(steps))


def collect(frame, indicator_cls, lines, **kwargs):
    """Run one indicator over one feed, returning a frame of its line values."""
    rows = []

    class Probe(bt.Strategy):
        def __init__(self):
            self.ind = indicator_cls(self.data, **kwargs)

        def next(self):
            rows.append({name: getattr(self.ind, name)[0] for name in lines})

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=frame))
    cerebro.addstrategy(Probe)
    cerebro.run()
    return pd.DataFrame(rows, columns=list(lines))


def pandas_stoch_rsi(close, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    """Independent reference implementation, built only from pandas."""
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / rsi_period, adjust=False).mean()
    rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    low = rsi.rolling(stoch_period).min()
    high = rsi.rolling(stoch_period).max()
    span = (high - low).replace(0.0, np.nan)
    raw = (100.0 * (rsi - low) / span).fillna(0.0)

    perc_k = raw.rolling(smooth_k).mean()
    perc_d = perc_k.rolling(smooth_d).mean()
    return rsi, perc_k, perc_d


# --------------------------------------------------------------------------
# StochasticRsi
# --------------------------------------------------------------------------


def test_matches_an_independent_pandas_implementation():
    close = gbm(11)
    got = collect(make_frame(close), StochasticRsi, ("percK", "percD", "rsi"))
    want_rsi, want_k, want_d = pandas_stoch_rsi(close)

    # Compare on the tail, where every warm-up window is fully populated.
    tail = 100
    assert got["rsi"].values[-tail:] == pytest.approx(want_rsi.values[-tail:], abs=1e-9)
    assert got["percK"].values[-tail:] == pytest.approx(want_k.values[-tail:], abs=1e-9)
    assert got["percD"].values[-tail:] == pytest.approx(want_d.values[-tail:], abs=1e-9)


def test_percent_lines_stay_within_zero_and_one_hundred():
    got = collect(make_frame(gbm(12)), StochasticRsi, ("percK", "percD"))
    assert got["percK"].min() >= 0.0 and got["percK"].max() <= 100.0
    assert got["percD"].min() >= 0.0 and got["percD"].max() <= 100.0


def test_no_nan_or_inf_is_produced():
    got = collect(make_frame(gbm(13)), StochasticRsi, ("percK", "percD", "rsi"))
    assert np.isfinite(got.to_numpy()).all()


def test_flat_price_reports_a_flat_oscillator():
    """Regression: a constant price used to report a confident %K of 100.

    Pine guards the degenerate window with an exact ``highest - lowest == 0``.
    That is not enough in floating point. Wilder smoothing decays average gain
    and average loss at the same rate, so their ratio — and therefore RSI —
    holds constant on a flat price, but only to within rounding: the observed
    range is about 1e-14, not 0. The exact test misses, the division amplifies
    that noise across the full 0-100 range, and the indicator claims a maximal
    reading for a price that has not moved. Hence the epsilon.
    """
    close = np.concatenate([gbm(14, n=200), np.full(120, 100.0)])
    got = collect(make_frame(close), StochasticRsi, ("percK", "percD", "rsi"))

    assert np.isfinite(got.to_numpy()).all()

    flat = got.iloc[-100:]
    # The premise: RSI is constant here only up to float noise, not exactly.
    assert 0.0 < flat["rsi"].max() - flat["rsi"].min() < StochasticRsi.FLAT_EPS
    # And so the oscillator must read flat rather than amplifying that noise.
    assert flat["percK"].iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert flat["percD"].iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_the_epsilon_guard_does_not_disturb_normal_data():
    """Real movement is orders of magnitude above the epsilon, so nothing shifts."""
    close = gbm(16)
    got = collect(make_frame(close), StochasticRsi, ("percK",))
    _, want_k, _ = pandas_stoch_rsi(close)
    assert got["percK"].values[-100:] == pytest.approx(want_k.values[-100:], abs=1e-9)


def test_periods_are_configurable():
    frame = make_frame(gbm(15))
    default = collect(frame, StochasticRsi, ("percK",))
    slower = collect(frame, StochasticRsi, ("percK",), rsi_period=21, stoch_period=21)
    # Different windows must give a different oscillator, and a longer warm-up.
    assert len(slower) < len(default)
    assert not np.allclose(default["percK"].values[-50:], slower["percK"].values[-50:])


# --------------------------------------------------------------------------
# EmaRsiStochRsiSignal
# --------------------------------------------------------------------------


def test_entry_and_exit_are_binary():
    got = collect(make_frame(gbm(21)), EmaRsiStochRsiSignal, ("entry", "exit"))
    assert set(np.unique(got["entry"].values)) <= {0.0, 1.0}
    assert set(np.unique(got["exit"].values)) <= {0.0, 1.0}


def test_every_entry_satisfies_all_of_its_conditions():
    """The conjunction is the whole point, so verify it bar by bar."""
    close = gbm(22, n=900)
    frame = make_frame(close)
    rows = []

    class Probe(bt.Strategy):
        def __init__(self):
            self.sig = EmaRsiStochRsiSignal(self.data)
            self.stoch = StochasticRsi(self.data)
            self.ema = bt.indicators.EMA(self.data, period=20)
            self.cross = bt.indicators.CrossOver(self.stoch.percK, self.stoch.percD)

        def next(self):
            rows.append(
                {
                    "entry": self.sig.entry[0],
                    "cross": self.cross[0],
                    "k": self.stoch.percK[0],
                    "rsi": self.stoch.rsi[0],
                    "rsi_prev": self.stoch.rsi[-1],
                    "ema": self.ema[0],
                    "ema_prev": self.ema[-1],
                }
            )

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=frame))
    cerebro.addstrategy(Probe)
    cerebro.run()

    frame = pd.DataFrame(rows)
    entries = frame[frame["entry"] == 1.0]
    assert (
        not entries.empty
    ), "fixture produced no entries; the assertions below are vacuous"
    assert (entries["cross"] == 1.0).all()
    assert (entries["k"] < 30.0).all()
    assert (entries["rsi"] > entries["rsi_prev"]).all()
    assert (entries["ema"] > entries["ema_prev"]).all()


def test_dropping_the_rsi_filter_can_only_add_entries():
    frame = make_frame(gbm(23, n=900))
    strict = collect(frame, EmaRsiStochRsiSignal, ("entry",))["entry"].sum()
    loose = collect(frame, EmaRsiStochRsiSignal, ("entry",), require_rsi_rising=False)[
        "entry"
    ].sum()
    assert loose >= strict


def test_disabling_the_trend_filter_can_only_add_entries():
    frame = make_frame(gbm(24, n=900))
    filtered = collect(frame, EmaRsiStochRsiSignal, ("entry",))["entry"].sum()
    unfiltered = collect(frame, EmaRsiStochRsiSignal, ("entry",), trend_filter=False)[
        "entry"
    ].sum()
    assert unfiltered >= filtered


def test_raising_the_oversold_bound_can_only_add_entries():
    frame = make_frame(gbm(25, n=900))
    tight = collect(frame, EmaRsiStochRsiSignal, ("entry",))["entry"].sum()
    wide = collect(frame, EmaRsiStochRsiSignal, ("entry",), oversold=60.0)[
        "entry"
    ].sum()
    assert wide >= tight


def test_trend_lookback_of_one_is_the_close_above_ema_identity():
    """EMA_t - EMA_{t-1} = alpha * (close_t - EMA_{t-1}), so the two coincide."""
    frame = make_frame(gbm(26, n=600))
    rows = []

    class Probe(bt.Strategy):
        def __init__(self):
            self.ema = bt.indicators.EMA(self.data, period=20)

        def next(self):
            rows.append(
                {
                    "rising": float(self.ema[0] > self.ema[-1]),
                    "above_prev": float(self.data.close[0] > self.ema[-1]),
                }
            )

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=frame))
    cerebro.addstrategy(Probe)
    cerebro.run()

    got = pd.DataFrame(rows)
    assert (got["rising"] == got["above_prev"]).all()


def test_trend_lookback_changes_the_filter():
    frame = make_frame(gbm(27, n=1200))
    counts = {
        lookback: collect(
            frame, EmaRsiStochRsiSignal, ("entry",), trend_lookback=lookback
        )["entry"].sum()
        for lookback in (1, 10, 20)
    }
    assert len(set(counts.values())) > 1, f"lookback had no effect: {counts}"


def test_trend_break_exit_is_off_by_default_and_adds_exits_when_on():
    frame = make_frame(gbm(28, n=900))
    default = collect(frame, EmaRsiStochRsiSignal, ("exit",))["exit"].sum()
    with_break = collect(
        frame, EmaRsiStochRsiSignal, ("exit",), exit_on_trend_break=True
    )["exit"].sum()
    assert with_break > default


def test_a_trend_lookback_below_one_is_rejected():
    with pytest.raises(ValueError, match="trend_lookback must be >= 1"):
        collect(
            make_frame(gbm(29, n=100)),
            EmaRsiStochRsiSignal,
            ("entry",),
            trend_lookback=0,
        )


# --------------------------------------------------------------------------
# integration with the portfolio strategies
# --------------------------------------------------------------------------


def test_signal_drives_the_equal_weight_entry_exit_portfolio():
    """The line names must match what the portfolio strategy expects."""
    cerebro = bt.Cerebro()
    for seed in range(31, 35):
        cerebro.adddata(
            bt.feeds.PandasData(dataname=make_frame(gbm(seed, n=700))), name=f"A{seed}"
        )
    cerebro.broker.setcash(100_000.0)
    cerebro.addstrategy(
        EqualWeightEntryExitPortfolio,
        total_days=700,
        indicator_cls=EmaRsiStochRsiSignal,
        indicator_kwargs={},
    )
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    strategy = cerebro.run()[0]

    assert cerebro.broker.getvalue() > 0
    closed = strategy.analyzers.trades.get_analysis().get("total", {}).get("closed", 0)
    assert closed > 0, "the signal never opened and closed a position"


def test_portfolio_respects_the_leverage_cap():
    cerebro = bt.Cerebro()
    for seed in range(41, 45):
        cerebro.adddata(
            bt.feeds.PandasData(dataname=make_frame(gbm(seed, n=700))), name=f"B{seed}"
        )
    cerebro.broker.setcash(100_000.0)
    cerebro.addstrategy(
        EqualWeightEntryExitPortfolio,
        total_days=700,
        leverage=0.9,
        indicator_cls=EmaRsiStochRsiSignal,
        indicator_kwargs={},
    )
    strategy = cerebro.run()[0]

    # Never borrowed: cash stays non-negative across the run.
    assert strategy.broker.getcash() >= 0
