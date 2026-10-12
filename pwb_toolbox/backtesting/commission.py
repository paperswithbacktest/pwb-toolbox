"""Per-symbol trading costs for the backtest harness.

Costs are read from measured data where it exists, and only estimated where it
does not. That order matters: the estimator this module used to rely on is
unusable on liquid names, and it was the only source.

What was wrong with estimating
------------------------------
The previous version ran Roll (1984) on daily returns inside what it called a
Gibbs sampler, then divided the result by ten. Three things were wrong, each
measured:

* **The sampler was not one.** It drew trade directions from
  ``np.random.normal(loc=c, scale=sqrt(sigma_u))`` -- a law that does not depend
  on the data. The regression on those random signs returns a slope of ~0, the
  residuals are the raw returns again, and ``c`` is recomputed identically every
  iteration. On a 2 000-point simulation Roll gives 0.001577 and the "Gibbs"
  0.001576: a 0.10 % difference for 1 000 iterations.

* **Roll cannot work on daily bars for liquid names.** The quantity sought is
  ``-(s/2)^2`` and the noise in estimating a lag-1 autocovariance is ``σ²/√n``.
  For a 2 %-daily-vol stock with a 2 bp spread the noise is six times the
  signal, and ``sqrt(max(0, -cov))`` then returns exactly zero. Measured on the
  9 060 US names with 240+ sessions in 2024: **54.7 % of names above $50 priced
  at zero**, and where it did return a number it said 32 bp against 12 bp
  actually measured from quotes. Below $5 it lands on 176.5 bp against 175 --
  right, but only because that is the one regime where the spread dominates
  volatility.

* **A zero estimate was kept as a zero cost.** ``0.0`` is finite, so it was
  stored rather than replaced by the pool median: half the liquid universe
  traded free. "No estimate" and "no cost" are different statements and are now
  kept apart -- ``roll_half_spread`` returns ``None``.

The division by ten had no justification anywhere in the code and is gone.

What replaces it
----------------
``paperswithbacktest/Stocks-Yearly-TransactionCostParams`` carries a spread per
symbol **and per year**, measured on trades and quotes. That fixes the zeros,
the factor of three, and the staleness: one estimate computed on 2020+ data was
being applied to thirty-five years of history, across the 2001 decimalisation
that changed spreads by an order of magnitude.

Coverage, measured: **99.4 %** of the symbols in the merged daily panel, and
**94.4 %** of symbol mentions weighted by how often strategies cite them. Roll
is now a genuine fallback rather than the main path.

Every lookup reports which source answered, so a backtest can say whether a
break-even rests on a measurement or on an estimate.
"""

from __future__ import annotations

from collections import namedtuple
import os

import backtrader as bt
import numpy as np
import pandas as pd

from ..datasets import get_pricing

_MIN_OBS = 5  # need at least this many returns to attempt Roll
_EPS = 1e-12

# Spread source, cheapest and most trustworthy first.
SOURCE_MEASURED = "measured"      # from the per-year dataset
SOURCE_ROLL = "roll"              # estimated from daily closes
SOURCE_DEFAULT = "default"        # pool median, or the floor below

# Used when nothing else answers: one basis point each way.
FALLBACK_HALF_SPREAD = 1e-4

COST_PARAMS_REPO = "paperswithbacktest/Stocks-Yearly-TransactionCostParams"

Cost = namedtuple("Cost", "symbol half_spread source year")


# --------------------------------------------------------------------------- #
# Estimation (fallback only)
# --------------------------------------------------------------------------- #

def roll_half_spread(price_changes) -> float | None:
    """Roll (1984) half-spread from the lag-1 autocovariance of price changes.

    Returns ``None`` -- not zero -- when the autocovariance is non-negative, so
    an absent estimate cannot be mistaken for a free trade. On daily bars that
    happens for roughly half of liquid names.
    """
    pc = np.asarray(price_changes, dtype=float)
    pc = pc[np.isfinite(pc)]
    if pc.size < max(3, _MIN_OBS):
        return None
    lead, lag = pc[1:], pc[:-1]
    cov = float(((lead - lead.mean()) * (lag - lag.mean())).mean())
    if not np.isfinite(cov) or cov >= 0:
        return None
    return float(np.sqrt(-cov))


# --------------------------------------------------------------------------- #
# Measured parameters
# --------------------------------------------------------------------------- #

def _read_hub_table(repo_id: str) -> pd.DataFrame:
    """Read a dataset's parquet shards straight from the Hub.

    Deliberately **not** via ``from datasets import load_dataset``. The papers
    repository carries its own ``datasets.py``, which shadows the Hugging Face
    package whenever a backtest runs from that directory -- the import then
    fails, this module falls back to Roll for every symbol, and the only trace
    is a printed warning. Going through ``huggingface_hub`` and pandas removes
    the name clash, and the table is one small parquet anyway.
    """
    import huggingface_hub

    token = os.getenv("HF_ACCESS_TOKEN")
    files = [
        f
        for f in huggingface_hub.list_repo_files(repo_id, repo_type="dataset", token=token)
        if f.startswith("data/") and f.endswith(".parquet")
    ]
    if not files:
        raise FileNotFoundError(f"{repo_id} carries no parquet under data/")
    frames = [
        pd.read_parquet(
            huggingface_hub.hf_hub_download(
                repo_id, path, repo_type="dataset", token=token
            )
        )
        for path in sorted(files)
    ]
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


_PARAMS_CACHE: dict | None = None
_LAMBDA_CACHE: dict | None = None


def load_cost_params(repo_id: str = COST_PARAMS_REPO) -> dict:
    """``{(symbol, year): spread_bps}`` from the Hub, loaded once per process.

    A missing or unreachable dataset is not fatal: the caller falls back to
    Roll, and says so.
    """
    global _PARAMS_CACHE
    if _PARAMS_CACHE is not None:
        return _PARAMS_CACHE
    try:
        frame = _read_hub_table(repo_id)
        frame = frame[frame["spread_bps"].notna()]
        _PARAMS_CACHE = {
            (s, int(y)): float(v)
            for s, y, v in zip(frame["symbol"], frame["year"], frame["spread_bps"])
        }
    except Exception as exc:  # noqa: BLE001 - absence is a degraded mode, not a crash
        print(f"[costs] measured parameters unavailable ({exc}); falling back to Roll")
        _PARAMS_CACHE = {}
    return _PARAMS_CACHE


def measured_half_spread(symbol: str, year: int, params: dict | None = None):
    """Half of the measured spread, as a fraction of price, or ``None``.

    The dataset stores a full spread in basis points; a round trip crosses half
    of it on each side.
    """
    params = load_cost_params() if params is None else params
    spread_bps = params.get((symbol, int(year)))
    if spread_bps is None or not np.isfinite(spread_bps) or spread_bps <= 0:
        return None
    return float(spread_bps) / 2.0 / 1e4


def _nearest_year(symbol: str, year: int, params: dict, max_gap: int = 3):
    """Fall back to the closest year within ``max_gap`` for the same symbol.

    Spreads move slowly year to year; they do not survive a decade. Three years
    is close enough to be informative and short enough to stay on the same side
    of the 2001 decimalisation.
    """
    for gap in range(1, max_gap + 1):
        for candidate in (year - gap, year + gap):
            value = measured_half_spread(symbol, candidate, params)
            if value is not None:
                return value, candidate
    return None, None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def get_cost_breakdown(symbols, start_date="2020-01-01", year=None) -> dict:
    """``{symbol: Cost}`` -- the half-spread and where it came from.

    ``year`` selects the measured vintage; it defaults to the year of
    ``start_date``. Pass the year of the slice being traded to get the spread
    that actually prevailed then, rather than today's.
    """
    if year is None:
        year = int(str(start_date)[:4])
    params = load_cost_params()

    out: dict[str, Cost] = {}
    needs_roll = []
    for symbol in symbols:
        value = measured_half_spread(symbol, year, params)
        if value is not None:
            out[symbol] = Cost(symbol, value, SOURCE_MEASURED, year)
            continue
        value, found_year = _nearest_year(symbol, year, params)
        if value is not None:
            out[symbol] = Cost(symbol, value, SOURCE_MEASURED, found_year)
        else:
            needs_roll.append(symbol)

    if needs_roll:
        out.update(_roll_for(needs_roll, start_date))

    # Anything still unresolved gets the median of what was resolved, which is
    # a statement about the universe rather than about the symbol -- so it is
    # labelled SOURCE_DEFAULT and never silently blended in.
    resolved = [c.half_spread for c in out.values() if c.source != SOURCE_DEFAULT]
    default = float(np.median(resolved)) if resolved else FALLBACK_HALF_SPREAD
    for symbol in symbols:
        if symbol not in out:
            out[symbol] = Cost(symbol, default, SOURCE_DEFAULT, year)
    return out


def _roll_for(symbols, start_date) -> dict:
    """Estimate from daily closes, for the symbols the dataset does not cover."""
    out: dict[str, Cost] = {}
    try:
        df = get_pricing(
            symbol_list=list(symbols),
            fields=["open", "high", "low", "close"],
            start_date=start_date,
            extend=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[costs] pricing unavailable for the Roll fallback ({exc})")
        return out
    if df is None or df.empty:
        return out
    try:
        available = set(df.columns.get_level_values(0))
    except Exception:  # noqa: BLE001 - non-MultiIndex frame
        available = set(df.columns)

    for symbol in symbols:
        if symbol not in available:
            continue
        close = (
            pd.to_numeric(df[symbol].close, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        close = close[close > 0]
        if close.size < _MIN_OBS + 1:
            continue
        value = roll_half_spread(np.diff(np.log(close.values)))
        if value is not None and value > _EPS:
            out[symbol] = Cost(symbol, float(value), SOURCE_ROLL, None)
    return out


class SpreadImpactCommission(bt.CommInfoBase):
    """Half-spread always, Kyle impact only when explicitly enabled.

    ``cost = notional * half_spread + book_avg_factor * lambda_bps *
    (notional / 1e6) * notional / 1e4``

    The second term is the average price concession from walking a linear book
    whose slope is ``lambda_bps`` basis points per $1M of net flow -- hence the
    one-half in ``book_avg_factor``: the terminal move is paid only by the last
    share.

    **It is off by default, and that is deliberate.** The notional here is real
    -- backtrader knows the order size -- but it is real relative to the ``cash``
    the strategy was handed, and most published backtests pass an arbitrary
    figure. Charging impact against an invented capital would produce a number
    that looks rigorous and means nothing. Turn it on when the capital is the
    one you actually intend to deploy.
    """

    params = (
        ("half_spread", FALLBACK_HALF_SPREAD),
        ("lambda_bps", 0.0),
        ("book_avg_factor", 0.5),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )

    def _getcommission(self, size, price, pseudoexec):
        notional = abs(size) * price
        cost = notional * self.p.half_spread
        if self.p.lambda_bps > 0:
            impact_bps = self.p.book_avg_factor * self.p.lambda_bps * (notional / 1e6)
            cost += notional * impact_bps / 1e4
        return cost


def load_lambda_params(repo_id: str = COST_PARAMS_REPO) -> dict:
    """``{(symbol, year): lambda_bps}`` -- Kyle's slope, for the impact term."""
    global _LAMBDA_CACHE
    if _LAMBDA_CACHE is not None:
        return _LAMBDA_CACHE
    try:
        frame = _read_hub_table(repo_id)
        frame = frame[frame["lambda_bps"].notna()]
        _LAMBDA_CACHE = {
            (s, int(y)): float(v)
            for s, y, v in zip(frame["symbol"], frame["year"], frame["lambda_bps"])
            if float(v) > 0
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[costs] lambda unavailable ({exc}); impact term disabled")
        _LAMBDA_CACHE = {}
    return _LAMBDA_CACHE


def get_commissions(symbols, start_date="2020-01-01", year=None) -> dict:
    """``{symbol: half_spread}`` as a fraction of price -- the harness's input.

    Backwards compatible in shape with the previous version, not in value: the
    unjustified division by ten is gone, measured spreads are preferred, and a
    symbol Roll cannot price no longer trades for free.
    """
    return {s: c.half_spread for s, c in get_cost_breakdown(symbols, start_date, year).items()}


def cost_sources(symbols, start_date="2020-01-01", year=None) -> dict:
    """``{source: count}`` -- what a backtest should report alongside its costs."""
    counts: dict[str, int] = {}
    for cost in get_cost_breakdown(symbols, start_date, year).values():
        counts[cost.source] = counts.get(cost.source, 0) + 1
    return counts


if __name__ == "__main__":
    for symbol, cost in get_cost_breakdown(
        ["AAPL", "MSFT", "GOOGL", "NOTATICKER"], year=2010
    ).items():
        print(f"{symbol:<12} {cost.half_spread * 1e4:>8.2f} bp  {cost.source} {cost.year or ''}")
