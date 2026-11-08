"""Option half spreads come from Options-Yearly-TransactionCostParams, with the
same lookup and fallbacks as the literal tables the option strategies carried."""

import itertools
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.backtesting.option_costs as oc
from pwb_toolbox.backtesting.commission import SOURCE_EXTRAPOLATED, SOURCE_MEASURED

PRICE_LOWS = (0.0, 0.10, 0.50, 1.0, 2.0, 5.0, 10.0, 25.0)
VOLUME_LOWS = (0.0, 1e3, 1e4, 1e5, 1e6)

# Synthetic tables in the strategies' literal layout: {key: (near row, far row)}.
TIERS = {
    t: (tuple(round(0.01 * (5 - t) * (b + 1), 3) for b in range(8)),
        tuple(round(0.015 * (5 - t) * (b + 1), 3) for b in range(8)))
    for t in range(5)
}
OWN = {
    "SPY": (tuple(0.005 * (b + 1) for b in range(8)), tuple(0.007 * (b + 1) for b in range(8))),
    "META": (tuple(0.02 * (b + 1) for b in range(8)), tuple(0.03 * (b + 1) for b in range(8))),
}


def _rows(year, symbol, tier, rows, methods=None):
    out = []
    for m, row in zip(("near", "far"), rows):
        for b, value in enumerate(row):
            out.append({
                "symbol": symbol, "tier": tier, "year": year, "moneyness": m,
                "price_min": PRICE_LOWS[b],
                "price_max": PRICE_LOWS[b + 1] if b + 1 < 8 else None,
                "half_spread": value,
                "method": (methods or {}).get((m, b), "measured"),
                "volume_min": VOLUME_LOWS[tier],
                "volume_max": VOLUME_LOWS[tier + 1] if tier + 1 < 5 else None,
            })
    return out


def _table(years=(2026,), tiers=TIERS, own=OWN, fallback=None):
    rows = []
    for year in years:
        for t, r in tiers.items():
            rows += _rows(year, None, t, r)
        for u, r in own.items():
            rows += _rows(year, u, 4, r, fallback if u == "META" else None)
    return pd.DataFrame(rows)


def _legacy(tiers, own):
    """The function the option strategies carried, verbatim but for its tables."""
    PRICE_EDGES = (0.10, 0.50, 1.0, 2.0, 5.0, 10.0, 25.0)
    VOLUME_TIERS = (1e3, 1e4, 1e5, 1e6)

    def half_spread(price, otm, tier, underlying=None):
        underlying = "META" if underlying == "FB" else underlying
        rows = own.get(underlying) or tiers[tier]
        row = rows[1] if abs(otm - 1.0) > 0.10 else rows[0]
        return min(row[int(np.searchsorted(PRICE_EDGES, price, side="right"))], price)

    def volume_tier(daily_volume):
        return int(np.searchsorted(VOLUME_TIERS, daily_volume, side="right"))

    return half_spread, volume_tier


class OptionCostsTest(unittest.TestCase):
    def setUp(self):
        oc._MODEL_CACHE.clear()
        self.model = oc.OptionsCostModel(_table())

    def test_the_model_reproduces_the_literal_tables_cell_for_cell(self):
        legacy, legacy_tier = _legacy(TIERS, OWN)
        prices = [0.0, 0.01, 0.0999, 0.10, 0.1001, 0.3, 0.5, 0.75, 1.0, 1.99, 2.0, 4.0,
                  5.0, 9.99, 10.0, 24.0, 25.0, 25.01, 80.0, float("nan")]
        otms = [0.5, 0.8999, 0.9, 0.95, 1.0, 1.05, 1.1, 1.1001, 1.5, float("nan")]
        for price, otm, tier, und in itertools.product(
                prices, otms, range(5), [None, "SPY", "SPX", "FB", "META", "AAPL"]):
            want = legacy(price, otm, tier, und)
            got = self.model.half_spread(price, otm, tier=tier, underlying=und)
            if np.isnan(want):
                self.assertTrue(np.isnan(got))
            else:
                self.assertEqual(got, want, (price, otm, tier, und))
        for volume in [0, 999, 1000, 1001, 9999, 1e4, 5e4, 1e5, 1e6, 1e6 + 1, 1e9]:
            self.assertEqual(self.model.volume_tier(volume), legacy_tier(volume), volume)

    def test_an_underlying_row_wins_over_the_tier(self):
        cost = self.model.breakdown(0.3, 1.0, tier=0, underlying="SPY")
        self.assertEqual(cost.half_spread, OWN["SPY"][0][1])
        self.assertEqual(cost.segment, oc.SEGMENT_UNDERLYING)
        cost = self.model.breakdown(0.3, 1.0, tier=0, underlying="XYZ")
        self.assertEqual(cost.half_spread, TIERS[0][0][1])
        self.assertEqual(cost.segment, oc.SEGMENT_TIER)

    def test_fb_reads_meta(self):
        self.assertEqual(self.model.half_spread(3.0, 1.3, underlying="FB"), OWN["META"][1][4])

    def test_the_tier_can_come_from_the_volume(self):
        self.assertEqual(self.model.half_spread(0.3, 1.0, daily_volume=50_000),
                         TIERS[2][0][1])
        with self.assertRaises(ValueError):
            self.model.half_spread(0.3, 1.0, underlying="XYZ")

    def test_never_more_than_the_price(self):
        self.assertEqual(self.model.half_spread(0.004, 1.0, tier=0), 0.004)

    def test_years_measured_extrapolated_and_latest(self):
        model = oc.OptionsCostModel(pd.concat([
            _table(years=(2016,), tiers={t: tuple(tuple(v * 2 for v in r) for r in rows)
                                         for t, rows in TIERS.items()}),
            _table(years=(2026,)),
        ]))
        self.assertEqual(model.years, (2016, 2026))
        latest = model.breakdown(1.5, 1.0, tier=1)
        self.assertEqual((latest.year, latest.source), (2026, SOURCE_MEASURED))
        early = model.breakdown(1.5, 1.0, tier=1, year=2016)
        self.assertEqual((early.year, early.source), (2016, SOURCE_MEASURED))
        self.assertEqual(early.half_spread, 2 * TIERS[1][0][3])
        for year, used in [(2014, 2016), (2019, 2016), (2021, 2026), (2023, 2026), (2030, 2026)]:
            cost = model.breakdown(1.5, 1.0, tier=1, year=year)
            self.assertEqual((cost.year, cost.source), (used, SOURCE_EXTRAPOLATED), year)
        self.assertEqual(model.resolve_year(2021), (2026, SOURCE_EXTRAPOLATED))  # tie: later

    def test_the_method_of_the_cell_is_reported(self):
        model = oc.OptionsCostModel(_table(fallback={("far", 7): "tier_fallback"}))
        self.assertEqual(model.breakdown(40.0, 1.3, underlying="META").method, "tier_fallback")
        self.assertEqual(model.breakdown(40.0, 1.0, underlying="META").method, "measured")

    def test_an_incomplete_table_is_refused(self):
        table = _table()
        with self.assertRaises(ValueError):
            oc.OptionsCostModel(table.iloc[1:])
        with self.assertRaises(ValueError):
            oc.OptionsCostModel(table[table["tier"] != 3])
        with self.assertRaises(ValueError):
            oc.OptionsCostModel(table.drop(columns=["method"]))

    def test_loaded_once_and_an_unreachable_table_raises(self):
        with mock.patch.object(oc, "_read_cost_table", return_value=_table()) as read:
            first = oc.load_options_cost_model()
            second = oc.load_options_cost_model()
            self.assertIs(first, second)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(oc.options_half_spread(0.3, 1.0, underlying="SPY"), OWN["SPY"][0][1])
            self.assertEqual(oc.option_volume_tier(2e6), 4)
            read.assert_called_once_with(oc.OPTIONS_PARAMS_REPO)
        oc._MODEL_CACHE.clear()
        with mock.patch.object(oc, "_read_cost_table", side_effect=OSError("404")):
            with self.assertRaises(RuntimeError):
                oc.options_half_spread(0.3, 1.0, tier=1)

    def test_exported_from_the_backtesting_package(self):
        from pwb_toolbox import backtesting

        for name in ("options_half_spread", "options_cost_breakdown", "option_volume_tier",
                     "load_options_cost_model", "OptionsCostModel", "OPTIONS_PARAMS_REPO"):
            self.assertTrue(hasattr(backtesting, name), name)


if __name__ == "__main__":
    unittest.main()
