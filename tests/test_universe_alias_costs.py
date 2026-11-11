"""The members of a universe alias are priced at their measured spread.

Up to 0.1.47 the harness judged the strategy's own symbol list, and a list
that reads ``["sp500"]`` holds no equity name: ``equity_symbols`` returned
``{"sp500"}``, the ~1 900 members ``get_pricing`` loaded were all judged
off-class, and every one was charged the 1 bp floor. The run logs said
``Commissions: 1936 symbols ... (1936 default)``.

Offline: the point-in-time member list, the catalogue index and the cost
table are all replaced.
"""

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.backtesting.commission as cm
import pwb_toolbox.datasets as pwb_ds
import pwb_toolbox.datasets.pit_universe as pit
from pwb_toolbox.backtesting import backtest_engine as be

MEMBERS = ["AAPL", "AET", "ETH", "MSFT", "YHOO"]

# ``ETH`` is listed as a crypto by this index on purpose: a member is a stock
# whatever else the index files under the same ticker. ``AET`` and ``YHOO`` are
# absent from it, like the delisted names the universe exists to bring back.
INDEX = {
    "AAPL": "Stocks-Daily-Price",
    "MSFT": "Stocks-Daily-Price",
    "ETH": "Cryptocurrencies-Daily-Price",
    "SPY": "ETFs-Daily-Price",
    "BTC": "ETFs-Daily-Price",
    "EURUSD": "Forex-Daily-Price",
    "GC1": "Commodities-Daily-Price",
}

VINTAGES = {
    s: {2020: 0.0005, 2021: 0.0004} for s in MEMBERS + ["SPY", "BTC"]
}


class AliasTest(unittest.TestCase):
    def setUp(self):
        cm._UNIVERSE_CACHE = dict(INDEX)
        self.patches = [
            mock.patch.object(pit, "pit_symbols", lambda top_n, min_months=0: list(MEMBERS)),
            mock.patch.object(pwb_ds, "SP500_SYMBOLS", ["AAPL", "MSFT", "ETH"]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        cm._UNIVERSE_CACHE = None


class CostClasses(AliasTest):
    def test_the_alias_as_written_is_what_failed(self):
        # The behaviour being fixed, kept visible: the raw list has no equity.
        self.assertEqual(cm.equity_symbols(["sp500"]), {"sp500"})

    def test_pit_members_are_equities(self):
        for alias in ("sp500", "liquid1000"):
            equities, currencies = cm.cost_classes([alias])
            self.assertTrue(set(MEMBERS) <= equities, alias)
            self.assertNotIn(alias, equities)
            self.assertEqual(currencies, {})

    def test_a_bare_string_is_one_symbol(self):
        equities, _ = cm.cost_classes("sp500")
        self.assertTrue(set(MEMBERS) <= equities)

    def test_a_member_is_never_a_currency_leg(self):
        equities, currencies = cm.cost_classes(["sp500"])
        self.assertIn("ETH", equities)
        self.assertNotIn("ETH", currencies)

    def test_names_beside_the_alias_keep_their_own_rule(self):
        equities, currencies = cm.cost_classes(["sp500", "SPY", "BTC.CRP", "EURUSD", "GC1"])
        self.assertTrue(set(MEMBERS) <= equities)
        self.assertIn("SPY", equities)
        self.assertNotIn("BTC", equities)
        self.assertNotIn("EURUSD", equities)
        self.assertNotIn("GC1", equities)
        self.assertEqual(currencies, {
            "BTC": "Cryptocurrencies-Daily-Price",
            "EURUSD": "Forex-Daily-Price",
        })

    def test_an_explicit_member_follows_the_index_like_any_bare_name(self):
        # Named by the caller, ETH is routed by the index, not as a member.
        equities, currencies = cm.cost_classes(["sp500", "ETH"])
        self.assertNotIn("ETH", equities)
        self.assertEqual(currencies, {"ETH": "Cryptocurrencies-Daily-Price"})

    def test_frozen_members_follow_the_bare_name_rule(self):
        equities, currencies = cm.cost_classes(["sp500-frozen"])
        self.assertEqual(equities, {"AAPL", "MSFT"})
        self.assertEqual(currencies, {"ETH": "Cryptocurrencies-Daily-Price"})

    def test_a_plain_list_is_unchanged(self):
        symbols = ["AAPL", "SPY", "BTC.CRP", "EURUSD", "GC1", "NOTINDEXED"]
        equities, currencies = cm.cost_classes(symbols)
        self.assertEqual(equities, cm.equity_symbols(symbols))
        self.assertEqual(currencies, cm.currency_symbols(symbols))


class _Broker:
    def __init__(self):
        self.schemes = {}

    def addcommissioninfo(self, scheme, name=None):
        self.schemes[name] = scheme


class HarnessCharges(AliasTest):
    def setUp(self):
        super().setUp()
        self.patches2 = [
            mock.patch.object(cm, "load_cost_params", return_value={}),
            mock.patch.object(cm, "_symbol_vintages", return_value=VINTAGES),
            mock.patch.object(cm, "_front_month_vintages", return_value={}),
            mock.patch.object(cm, "_currency_vintages", return_value={}),
            mock.patch.object(cm, "_roll_for", return_value={}),
        ]
        for p in self.patches2:
            p.start()

    def tearDown(self):
        for p in self.patches2:
            p.stop()
        super().tearDown()

    def _apply(self, symbols, loaded):
        broker = _Broker()
        out = io.StringIO()
        with redirect_stdout(out):
            schemes = be._apply_per_symbol_commissions(
                broker, symbols, "2020-01-01",
                feeds={s: None for s in loaded}, end_date="2021-12-31",
            )
        return schemes, out.getvalue()

    def test_sp500_members_pay_their_measured_spread(self):
        schemes, log = self._apply(["sp500", "SPY"], MEMBERS + ["SPY"])
        self.assertEqual(set(schemes), set(MEMBERS) | {"SPY"})
        for symbol in MEMBERS:
            self.assertEqual(schemes[symbol].p.half_spread, 0.0005, symbol)
            self.assertEqual(schemes[symbol].p.schedule[2021][0], 0.0004, symbol)
        self.assertIn("Commissions: 6 symbols", log)
        self.assertIn("(6 measured)", log)
        self.assertNotIn("default", log)

    def test_crypto_leg_beside_the_alias_keeps_the_floor(self):
        schemes, log = self._apply(["sp500", "BTC.CRP"], MEMBERS + ["BTC"])
        self.assertEqual(schemes["BTC"].p.half_spread, cm.FALLBACK_HALF_SPREAD)
        self.assertIsNone(schemes["BTC"].p.schedule)
        self.assertIn("(1 default, 5 measured)", log)


if __name__ == "__main__":
    unittest.main()
