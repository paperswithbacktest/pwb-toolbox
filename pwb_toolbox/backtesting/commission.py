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
import re

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
SOURCE_EXTRAPOLATED = "extrapolated"  # nearest vintage, more than max_gap away

# Used when nothing else answers: one basis point each way.
FALLBACK_HALF_SPREAD = 1e-4

COST_PARAMS_REPO = "paperswithbacktest/Stocks-Yearly-TransactionCostParams"
FUTURES_PARAMS_REPO = "paperswithbacktest/Futures-Yearly-FrontMonthCostParams"

# The cost table is measured on US equity venues, so only these two may be
# answered from it. Every other class has to fall through.
EQUITY_REPOS = ("Stocks-Daily-Price", "ETFs-Daily-Price")

# ``get_pricing``'s own suffix map, repeated rather than imported: the lookup
# has to agree with how the prices were actually routed, and a divergence here
# would be silent.
_SUFFIX_REPOS = {
    "CRP": "Cryptocurrencies-Daily-Price",
    "STK": "Stocks-Daily-Price",
    "CMD": "Commodities-Daily-Price",
    "IDX": "Indices-Daily-Price",
    "ETF": "ETFs-Daily-Price",
    "FXR": "Forex-Daily-Price",
    "BND": "Bonds-Daily-Price",
    "CRYPTO": "Cryptocurrencies-Daily-Price",
}

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
_VINTAGE_CACHE: dict | None = None


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


_UNIVERSE_CACHE: dict | None = None
_FUTURES_CACHE: dict | None = None


def _universe_repos() -> dict:
    """``{symbol: repo name}`` from the catalogue index, loaded once."""
    global _UNIVERSE_CACHE
    if _UNIVERSE_CACHE is not None:
        return _UNIVERSE_CACHE
    try:
        from ..datasets import load_dataset

        frame = load_dataset("Universe-Daily-Price")
        _UNIVERSE_CACHE = {
            str(sym): str(repo).split("/")[-1]
            for sym, repo in zip(frame["symbol"], frame["repo_id"])
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[costs] catalogue index unavailable ({exc}); not filtering by class")
        _UNIVERSE_CACHE = {}
    return _UNIVERSE_CACHE


def equity_symbols(symbols) -> set:
    """Base names the US equity cost table may answer for.

    Why a filter is needed at all
    -----------------------------
    ``get_pricing`` routes ``BTC.CRP`` to the crypto repository and then hands
    the feed back under the bare name ``BTC``. The suffix -- the only thing
    that said which asset this is -- is gone by the time costs are priced, and
    ``BTC`` is also a US-listed ETF that sits in the cost table at **119.6 bp**
    of median spread. ``XRP`` is there at 269 bp, ``SOL`` at 41, ``ETH`` at 17.

    Charging a crypto leg a micro-cap equity spread is not a small error: on
    the eight crypto strategies in the validation set it moved Sharpe by up to
    -0.433, and every one of those deltas was an artefact.

    The catalogue index cannot settle it on its own -- it resolves ``BTC`` to
    the ETF and ``ETH``, ``SOL``, ``XRP`` to stocks, which is the very
    ambiguity at issue. So the suffix wins where the caller gave one, and the
    index is consulted only for a bare symbol.
    """
    universe = _universe_repos()
    out = set()
    for symbol in symbols:
        name = str(symbol)
        if "." in name:
            base, _, suffix = name.rpartition(".")
            repo = _SUFFIX_REPOS.get(suffix.upper())
            if repo is not None:
                if repo in EQUITY_REPOS:
                    out.add(base)
                continue
            name = base or name
        repo = universe.get(name)
        # Absent from the index means no evidence either way. Allowing it keeps
        # an equity that the index has not caught up with on the measured path;
        # a non-equity that is absent has no prices either, so it never becomes
        # a feed.
        if repo is None or repo in EQUITY_REPOS:
            out.add(name)
    return out


_FUTURES_ROOT_RE = re.compile(r"^([A-Z]{1,4})\d+$")


def futures_root(symbol: str):
    """``"CL"`` for ``"CL1"``, or None when the symbol is not a futures series.

    The trailing digit is required, and that is the whole safeguard. ``ES`` is
    the CME E-mini root *and* the ticker of a US utility; ``GC`` is gold and
    also a listed company. Demanding ``ES1`` rather than ``ES`` is what keeps
    this from repeating the ``BTC`` collision in the other direction -- see
    ``equity_symbols`` for that one.
    """
    m = _FUTURES_ROOT_RE.match(str(symbol).upper())
    return m.group(1) if m else None


def _front_month_vintages() -> dict:
    """``{root: {year: half_spread}}`` for the front-month futures table.

    Keyed by contract **root**, because the per-contract table cannot answer
    the question a backtest asks. A contract's liquidity has a lifecycle, so
    its yearly row averages the months it was far-dated and wide with the
    months it was the front month and tight: measured on 2020-08-05 the active
    gold contract quotes at 0.81 bp, while the *minimum* across every ``GC``
    contract of 2020 reads 7.92 bp and the median 39.90 bp.

    An absent repository is not an error -- it degrades to the explicit floor,
    exactly as before this table existed.
    """
    global _FUTURES_CACHE
    if _FUTURES_CACHE is not None:
        return _FUTURES_CACHE
    try:
        frame = _read_hub_table(FUTURES_PARAMS_REPO)
        out: dict[str, dict[int, float]] = {}
        for symbol, year, spread_bps in zip(
            frame["symbol"], frame["year"], frame["spread_bps"]
        ):
            if not np.isfinite(spread_bps) or spread_bps <= 0:
                continue
            out.setdefault(str(symbol).upper(), {})[int(year)] = (
                float(spread_bps) / 2.0 / 1e4
            )
        _FUTURES_CACHE = out
    except Exception as exc:  # noqa: BLE001
        print(f"[costs] futures cost table unavailable ({exc}); using the floor")
        _FUTURES_CACHE = {}
    return _FUTURES_CACHE


def _symbol_vintages(params: dict) -> dict:
    """``{symbol: {year: half_spread}}`` -- invert the table once, not per lookup."""
    global _VINTAGE_CACHE
    if _VINTAGE_CACHE is not None:
        return _VINTAGE_CACHE
    out: dict[str, dict[int, float]] = {}
    for (symbol, year), spread_bps in params.items():
        if not np.isfinite(spread_bps) or spread_bps <= 0:
            continue
        out.setdefault(symbol, {})[int(year)] = float(spread_bps) / 2.0 / 1e4
    _VINTAGE_CACHE = out
    return out


def get_cost_schedules(
    symbols,
    start_date="2020-01-01",
    end_date=None,
    max_gap: int = 3,
    measurable=None,
) -> tuple[dict, dict]:
    """``({symbol: {year: half_spread}}, {symbol: Cost})`` over the traded span.

    Why this exists, and why ``get_cost_breakdown`` was not enough
    -------------------------------------------------------------
    ``get_cost_breakdown`` resolves **one** vintage, the year of ``start_date``,
    and the harness then charged it across the whole backtest. Measured on the
    published corpus, that silently disabled the dataset: **5 802 of the
    strategies start at ``1990-01-01``**, the table begins in 2003, and a
    three-year tolerance cannot bridge thirteen years -- so every one of them
    fell through to Roll on daily bars, the estimator this module exists to
    replace. A 32-strategy validation run came back with *zero* measured
    spreads for exactly this reason.

    So the spread is resolved **per calendar year of the span**, and the scheme
    looks up the year of the bar it is pricing. A year the table does not hold
    takes the nearest vintage it does, labelled ``measured`` within ``max_gap``
    and ``extrapolated`` beyond it.

    The extrapolation is not free and the label is there to say so: spreads
    before the 2001 decimalisation were **wider** than anything in the table,
    so a 1990s leg priced off 2003 is charged too little. That is still the
    better error -- Roll put VBK at 33 bp against 12.5 bp measured -- but a
    break-even that rests on an extrapolated vintage is not a measurement.
    """
    start_year = int(str(start_date)[:4])
    end_year = int(str(end_date)[:4]) if end_date is not None else start_year
    if end_year < start_year:
        start_year, end_year = end_year, start_year
    span = range(start_year, end_year + 1)

    vintages = _symbol_vintages(load_cost_params())
    futures = _front_month_vintages()
    schedules: dict[str, dict[int, float]] = {}
    summary: dict[str, Cost] = {}
    uncovered = []

    offclass = []
    for symbol in symbols:
        # ``measurable`` is how a crypto or forex leg is kept out of a table
        # measured on US equity venues; see ``equity_symbols``.
        if measurable is not None and symbol not in measurable:
            # Off the equity universe there is one table left to try: the
            # front-month futures one, keyed by root. Reaching it only from
            # here is deliberate -- a symbol already judged non-equity cannot
            # be a stock that merely looks like a contract root.
            root = futures_root(symbol)
            have = futures.get(root) if root else None
            if not have:
                offclass.append(symbol)
                continue
        else:
            have = vintages.get(symbol)
            if not have:
                uncovered.append(symbol)
                continue
        years = sorted(have)
        schedule, worst_gap, at_start = {}, 0, None
        for year in span:
            if year in have:
                schedule[year] = have[year]
                gap = 0
            else:
                nearest = min(years, key=lambda y: (abs(y - year), y))
                schedule[year] = have[nearest]
                gap = abs(nearest - year)
            worst_gap = max(worst_gap, gap)
            if at_start is None:
                at_start = schedule[year]
        schedules[symbol] = schedule
        source = SOURCE_MEASURED if worst_gap <= max_gap else SOURCE_EXTRAPOLATED
        summary[symbol] = Cost(symbol, at_start, source, start_year)

    if uncovered:
        summary.update(_roll_for(uncovered, start_date))

    # A symbol outside the equity universe gets the floor, not Roll, and not
    # the equity pool median either.
    #
    # Roll is documented in this module as unusable on daily bars, and off the
    # equity universe it is worse than unusable. Measured on the stablecoin
    # strategy in the validation set, Roll on near-constant prices returned
    # **12 to 62 bp** for assets that trade inside 2 bp, and drove its Sharpe
    # from +0.42 to -1.14. The equity pool median is no better: it is a
    # statement about US stocks.
    #
    # So these are charged FALLBACK_HALF_SPREAD and labelled `default`, which
    # is the honest reading -- there is no cost table for crypto, forex,
    # futures or bonds yet. It is roughly right for majors and too low for an
    # emerging-market cross or a small altcoin, which is why the count is
    # printed rather than buried.
    for symbol in offclass:
        summary[symbol] = Cost(symbol, FALLBACK_HALF_SPREAD, SOURCE_DEFAULT, start_year)

    resolved = [c.half_spread for c in summary.values() if c.source != SOURCE_DEFAULT]
    default = float(np.median(resolved)) if resolved else FALLBACK_HALF_SPREAD
    for symbol in symbols:
        if symbol not in summary:
            summary[symbol] = Cost(symbol, default, SOURCE_DEFAULT, start_year)
    return schedules, summary


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
        # ``{year: (half_spread, lambda_bps)}`` plus the feed to read the bar's
        # year from. With both set the rate follows the calendar instead of
        # being frozen at the backtest's start -- see ``get_cost_schedules``.
        ("schedule", None),
        ("data", None),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )

    def __init__(self):
        super().__init__()
        self._stamp = None
        self._rates = (self.p.half_spread, self.p.lambda_bps)

    def _rates_now(self):
        """The pair in force on the bar being priced, cached per bar.

        ``_getcommission`` runs on every order and every margin pre-check, so
        the date is converted once per bar rather than once per call.
        """
        schedule, data = self.p.schedule, self.p.data
        if not schedule or data is None:
            return self.p.half_spread, self.p.lambda_bps
        try:
            stamp = data.datetime[0]
        except (IndexError, AttributeError):
            return self.p.half_spread, self.p.lambda_bps
        if stamp != self._stamp:
            self._stamp = stamp
            self._rates = schedule.get(
                bt.num2date(stamp).year, (self.p.half_spread, self.p.lambda_bps)
            )
        return self._rates

    def _getcommission(self, size, price, pseudoexec):
        half_spread, lambda_bps = self._rates_now()
        notional = abs(size) * price
        cost = notional * half_spread
        if lambda_bps > 0:
            impact_bps = self.p.book_avg_factor * lambda_bps * (notional / 1e6)
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
