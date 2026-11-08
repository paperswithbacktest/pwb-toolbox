"""Half bid-ask spread of a listed US option, read from a published table.

``Options-Daily-Price`` holds trades, not quotes, so an option strategy fills at
the close and pays half the quoted spread on each side. Until this module, the
model behind that half spread was a literal pasted into every option strategy
(``HALF_SPREAD_BY_TIER`` and ``HALF_SPREAD_BY_UNDERLYING``). It now lives in
``paperswithbacktest/Options-Yearly-TransactionCostParams``, like the stock,
forex and crypto spreads in :mod:`pwb_toolbox.backtesting.commission`, and this
module reads it.

The model
---------
Half the quoted spread, **in dollars per share**, as a function of:

* the option's **price**, in eight bands (0.10, 0.50, 1, 2, 5, 10 and 25
  dollars as edges, lower edge inclusive);
* its **distance to the money**: ``otm`` is ``K/S`` for a call and ``S/K`` for
  a put, and the option is *near* when ``|otm - 1| <= 0.10``, *far* beyond;
* the **underlying**: its own row for the 50 underlyings with the largest
  option volume, otherwise its liquidity tier, from its mean daily option
  volume (``<1k, 1k-10k, 10k-100k, 100k-1M, >1M`` contracts, lower edge
  inclusive).

Never more than the option's price. The table also carries the cells of an
underlying with fewer than 20 quotes, filled with its tier's value and labelled
``tier_fallback``, so an underlying row is always complete.

Years
-----
Each row carries the year it was measured. A year in the table is used as is
(``source = "measured"``); any other year takes the **nearest measured year**
and is labelled ``"extrapolated"``, so a backtest can say its early-year costs
rest on a later measurement. With ``year=None`` the latest measurement is used.

Usage::

    from pwb_toolbox.backtesting import options_half_spread, option_volume_tier

    tier = option_volume_tier(mean_daily_option_volume)
    cost = 100 * options_half_spread(price, otm, tier=tier, underlying="SPY", year=2018)
"""

from __future__ import annotations

from collections import namedtuple
from bisect import bisect_right
import re

import numpy as np
import pandas as pd

from .commission import (
    SOURCE_EXTRAPOLATED,
    SOURCE_MEASURED,
    _read_cost_table,
    _why_unreachable,
)

OPTIONS_PARAMS_REPO = "paperswithbacktest/Options-Yearly-TransactionCostParams"

# Within this distance of 1, ``otm`` is near the money.
NEAR_THE_MONEY = 0.10

# The options table names an underlying as it was named at the time; the cost
# table names it as it is named today.
UNDERLYING_ALIASES = {"FB": "META"}

SEGMENT_UNDERLYING = "underlying"
SEGMENT_TIER = "tier"

OptionCost = namedtuple("OptionCost", "half_spread source year segment method")

# A liquidity-tier row is named ``tier_0`` to ``tier_4`` in the ``symbol``
# column: the catalogue loader drops a row without a symbol.
TIER_SYMBOL = re.compile(r"^tier_(\d+)$")

_COLUMNS = ("symbol", "tier", "year", "moneyness", "price_min", "half_spread",
            "method", "volume_min")


def _edges(values) -> tuple:
    """Interior edges of a band set, from the bands' lower bounds."""
    lows = sorted(set(float(v) for v in values))
    return tuple(lows[1:])


class OptionsCostModel:
    """The table, indexed for lookups in the inner loop of a backtest."""

    def __init__(self, table: pd.DataFrame):
        missing = [c for c in _COLUMNS if c not in table.columns]
        if missing:
            raise ValueError(f"options cost table is missing {missing}")
        if table.empty:
            raise ValueError("options cost table is empty")
        symbol = table["symbol"].astype(object)
        is_tier = symbol.isna() | symbol.astype(str).str.match(TIER_SYMBOL.pattern)
        table = table.assign(symbol=symbol.where(~is_tier, ""))
        self.price_edges = _edges(table["price_min"])
        tiers = table[is_tier]
        self.volume_edges = _edges(tiers["volume_min"])
        n_bands = len(self.price_edges) + 1

        # {(year, kind, key): (near row, far row)}, each row one value per band.
        self._rows: dict = {}
        self._methods: dict = {}
        for (year, symbol, tier), seg in table.groupby(["year", "symbol", "tier"], sort=False):
            kind, key = (SEGMENT_TIER, int(tier)) if symbol == "" else (SEGMENT_UNDERLYING, symbol)
            rows, methods = [], []
            for band in ("near", "far"):
                part = seg[seg["moneyness"] == band].sort_values("price_min")
                if len(part) != n_bands:
                    raise ValueError(f"{year} {key} {band}: {len(part)} price bands, "
                                     f"expected {n_bands}")
                rows.append(tuple(float(v) for v in part["half_spread"]))
                methods.append(tuple(str(v) for v in part["method"]))
            self._rows[(int(year), kind, key)] = tuple(rows)
            self._methods[(int(year), kind, key)] = tuple(methods)
        self.years = tuple(sorted({k[0] for k in self._rows}))
        for year in self.years:
            have = {k[2] for k in self._rows if k[0] == year and k[1] == SEGMENT_TIER}
            if have != set(range(len(self.volume_edges) + 1)):
                raise ValueError(f"{year}: tiers {sorted(have)} do not cover every volume band")

    # -- lookups ---------------------------------------------------------- #

    def volume_tier(self, daily_volume) -> int:
        """Liquidity tier of an underlying from its mean daily option volume."""
        return int(np.searchsorted(self.volume_edges, daily_volume, side="right"))

    def resolve_year(self, year=None):
        """``(year used, source)``: the year itself, or the nearest measured one."""
        if year is None:
            return self.years[-1], SOURCE_MEASURED
        year = int(year)
        if year in self.years:
            return year, SOURCE_MEASURED
        # Nearest; on a tie the later measurement, which is the one a reader
        # of the card would expect to be current.
        best = min(self.years, key=lambda y: (abs(y - year), -y))
        return best, SOURCE_EXTRAPOLATED

    def underlyings(self, year=None) -> list:
        """Underlyings with a row of their own in that year's measurement."""
        used, _ = self.resolve_year(year)
        return sorted(k[2] for k in self._rows if k[0] == used and k[1] == SEGMENT_UNDERLYING)

    def breakdown(self, price, otm, tier=None, underlying=None, year=None,
                  daily_volume=None) -> OptionCost:
        """The half spread of one option and what it rests on.

        ``tier`` (or ``daily_volume``, from which it is derived) is only needed
        when ``underlying`` has no row of its own.
        """
        used, source = self.resolve_year(year)
        name = UNDERLYING_ALIASES.get(underlying, underlying)
        key = (used, SEGMENT_UNDERLYING, name)
        if name is None or key not in self._rows:
            if tier is None:
                if daily_volume is None:
                    raise ValueError(
                        f"{underlying!r} has no row of its own in {used}: pass its "
                        "liquidity tier or its mean daily option volume")
                tier = self.volume_tier(daily_volume)
            key = (used, SEGMENT_TIER, int(tier))
            if key not in self._rows:
                raise ValueError(f"no tier {tier} in {used}")
        far = 1 if abs(otm - 1.0) > NEAR_THE_MONEY else 0
        band = bisect_right(self.price_edges, price) if price == price else len(self.price_edges)
        value = self._rows[key][far][band]
        return OptionCost(min(value, price), source, used, key[1], self._methods[key][far][band])

    def half_spread(self, price, otm, tier=None, underlying=None, year=None,
                    daily_volume=None) -> float:
        """Dollar half spread of one option quoted around ``price``; never above it."""
        return self.breakdown(price, otm, tier, underlying, year, daily_volume).half_spread


_MODEL_CACHE: dict = {}


def load_options_cost_model(repo_id: str = OPTIONS_PARAMS_REPO) -> OptionsCostModel:
    """The model from the Hub (or the subscriber API), loaded once per process.

    Unlike the stock table there is no estimator to fall back to: an option
    backtest that cannot read its costs would trade for free, so this raises.
    The download itself is cached on disk by ``huggingface_hub``.
    """
    model = _MODEL_CACHE.get(repo_id)
    if model is not None:
        return model
    try:
        table = _read_cost_table(repo_id)
    except Exception as exc:  # noqa: BLE001 - re-raised with what to do about it
        raise RuntimeError(f"[option costs] {_why_unreachable(repo_id, exc)}") from exc
    model = OptionsCostModel(table)
    _MODEL_CACHE[repo_id] = model
    return model


def options_half_spread(price, otm, tier=None, underlying=None, year=None,
                        daily_volume=None, model: OptionsCostModel | None = None) -> float:
    """Dollar half spread of one listed US option, never more than its price.

    ``otm`` is ``K/S`` for a call and ``S/K`` for a put. ``underlying`` selects
    its own row when the table has one (``FB`` reads ``META``'s); otherwise
    ``tier`` -- or ``daily_volume``, the underlying's mean daily option volume --
    selects the liquidity tier. ``year`` picks the measurement: the nearest
    measured year when that one is not, the latest when ``None``.
    """
    model = load_options_cost_model() if model is None else model
    return model.half_spread(price, otm, tier, underlying, year, daily_volume)


def options_cost_breakdown(price, otm, tier=None, underlying=None, year=None,
                           daily_volume=None, model: OptionsCostModel | None = None
                           ) -> OptionCost:
    """:func:`options_half_spread` with its provenance: source, year, segment, method."""
    model = load_options_cost_model() if model is None else model
    return model.breakdown(price, otm, tier, underlying, year, daily_volume)


def option_volume_tier(daily_volume, model: OptionsCostModel | None = None) -> int:
    """Liquidity tier, 0 to 4, of an underlying from its mean daily option volume."""
    model = load_options_cost_model() if model is None else model
    return model.volume_tier(daily_volume)
