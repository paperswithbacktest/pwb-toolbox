"""Forex and crypto legs are priced from their own tables, not the floor."""

import unittest
from unittest import mock

import pandas as pd

import pwb_toolbox.backtesting.commission as cm


def _table(repo_id):
    if repo_id == cm.FOREX_PARAMS_REPO:
        return pd.DataFrame({
            "symbol": ["EURUSD", "USDJPY", "USDJPY"],
            "year": [2020, 2020, 2021],
            "price": [1.14, 106.7, 109.8],
            "lambda_bps": [None, None, None],
            "spread_bps": [0.62, 0.58, 0.60],
        })
    if repo_id == cm.CRYPTO_PARAMS_REPO:
        return pd.DataFrame({
            "symbol": ["BTCUSD", "ETHUSD", "ZZZUSD"],
            "year": [2020, 2020, 2020],
            "price": [11000.0, 300.0, 1.0],
            "lambda_bps": [5.1, 21.0, 1.0],
            "spread_bps": [5.27, 3.20, 0.0],
        })
    raise FileNotFoundError(repo_id)


class CurrencyCostsTest(unittest.TestCase):
    def setUp(self):
        cm._CURRENCY_CACHE = None
        cm._UNIVERSE_CACHE = {
            "BTC": "Cryptocurrencies-Daily-Price",
            "EURUSD": "Forex-Daily-Price",
            "AAPL": "Stocks-Daily-Price",
        }
        self.patches = [
            mock.patch.object(cm, "_read_cost_table", side_effect=_table),
            mock.patch.object(cm, "load_cost_params", return_value={}),
            mock.patch.object(cm, "_front_month_vintages", return_value={}),
            mock.patch.object(cm, "_symbol_vintages", return_value={}),
            # An uncovered equity would otherwise load its prices for Roll.
            mock.patch.object(cm, "_roll_for", return_value={}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        cm._CURRENCY_CACHE = None
        cm._UNIVERSE_CACHE = None

    def test_currency_symbols_uses_the_suffix_then_the_index(self):
        out = cm.currency_symbols(["BTC.CRP", "USDJPY.FXR", "EURUSD", "AAPL", "ETH.STK"])
        self.assertEqual(out, {
            "BTC": "Cryptocurrencies-Daily-Price",
            "USDJPY": "Forex-Daily-Price",
            "EURUSD": "Forex-Daily-Price",
        })

    def test_keys_try_the_inverse_pair_and_the_usd_quote(self):
        self.assertEqual(cm._currency_keys("JPYUSD", "Forex-Daily-Price"), ["JPYUSD", "USDJPY"])
        self.assertEqual(cm._currency_keys("BTC", "Cryptocurrencies-Daily-Price"), ["BTCUSD", "BTC"])

    def test_schedules_price_currency_legs_from_their_tables(self):
        symbols = ["BTC", "JPYUSD", "EURUSD", "AAPL", "DOGE"]
        currencies = {
            "BTC": "Cryptocurrencies-Daily-Price",
            "JPYUSD": "Forex-Daily-Price",
            "EURUSD": "Forex-Daily-Price",
            "DOGE": "Cryptocurrencies-Daily-Price",
        }
        schedules, summary = cm.get_cost_schedules(
            symbols, start_date="2020-01-01", end_date="2021-12-31",
            measurable={"AAPL"}, currencies=currencies,
        )
        self.assertAlmostEqual(schedules["BTC"][2020], 5.27 / 2 / 1e4)
        self.assertEqual(summary["BTC"].source, cm.SOURCE_MEASURED)
        # The inverse spelling reaches the USDJPY rows, year by year.
        self.assertAlmostEqual(schedules["JPYUSD"][2020], 0.58 / 2 / 1e4)
        self.assertAlmostEqual(schedules["JPYUSD"][2021], 0.60 / 2 / 1e4)
        self.assertAlmostEqual(schedules["EURUSD"][2020], 0.62 / 2 / 1e4)
        # A coin the table never saw keeps the floor, labelled default.
        self.assertEqual(summary["DOGE"].half_spread, cm.FALLBACK_HALF_SPREAD)
        self.assertEqual(summary["DOGE"].source, cm.SOURCE_DEFAULT)

    def test_zero_spread_rows_are_not_a_free_trade(self):
        have = cm._currency_have("ZZZ", "Cryptocurrencies-Daily-Price")
        self.assertIsNone(have)

    def test_without_a_currencies_map_nothing_changes(self):
        _, summary = cm.get_cost_schedules(
            ["BTC"], start_date="2020-01-01", measurable=set(),
        )
        self.assertEqual(summary["BTC"].source, cm.SOURCE_DEFAULT)


if __name__ == "__main__":
    unittest.main()
