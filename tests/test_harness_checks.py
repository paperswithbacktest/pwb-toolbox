"""The four checks ``run_strategy`` attaches to every backtest.

Offline: the loader, the point-in-time table, the catalogue index and the cost
tables are all replaced. The strategies are strings run through ``exec``, as
the site and the catalogue's server run them -- which is also what keeps the
code of one test's strategy out of another's look-ahead analysis.
"""

import json
import os
import unittest
from collections import namedtuple
from string import Template
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.backtesting as pwb_bt
import pwb_toolbox.backtesting.checks as checks
import pwb_toolbox.backtesting.commission as cm
from pwb_toolbox.datasets import PIT_UNIVERSES
from pwb_toolbox.datasets import pit_universe

from _synthetic import offline, panel

N = 6 * 252  # six years of bars from 2015
GONE = 1000  # X stops trading here: bought out, delisted
NAMES = ("A", "B", "X")

INDEX = {"A": "Stocks-Daily-Price", "B": "Stocks-Daily-Price", "X": "Stocks-Daily-Price",
         "SPY": "ETFs-Daily-Price", "TLT": "ETFs-Daily-Price"}
VINTAGES = {s: {y: 0.0005 for y in range(2010, 2027)} for s in NAMES + ("SPY", "TLT")}

RUN = Template('''
import pwb_toolbox.backtesting as pwb_bt
from pwb_toolbox.backtesting import BaseStrategy


class Monthly(BaseStrategy):
    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True
        $init

    def next(self):
        super().next()
        $peek
        if len(self) % 21 == 1:
            names = [d for d in self.datas if self.is_tradable(d)]
            for d in self.datas:
                if d not in names:
                    self.order_target_percent(d, 0.0)
            for d in names:
                self.order_target_percent(d, 0.9 / len(names))


strategy = pwb_bt.run_strategy(
    indicator_cls=None, indicator_kwargs={}, strategy_cls=Monthly, strategy_kwargs={},
    symbols=$symbols, start_date="2015-01-01", cash=100_000.0, $extra
)
''')


def _prices(names=NAMES):
    rng = np.random.default_rng(11)
    closes = {}
    for name in names:
        series = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, N)))
        if name == "X":
            series[GONE:] = np.nan
        closes[name] = series
    return panel(closes, start="2015-01-01")


def _universe(prices):
    rows = []
    for i, day in enumerate(prices.index):
        for rank, name in enumerate(NAMES, start=1):
            if name == "X" and i >= GONE:
                continue
            rows.append((day, name, rank))
    return pd.DataFrame(rows, columns=["date", "symbol", "rank"])


def _by_id(result):
    return {item["id"]: item for item in result["items"]}


class _Harness(unittest.TestCase):
    def setUp(self):
        self.key = PIT_UNIVERSES["sp500"]
        self.saved = pit_universe._cache.get(self.key)
        self.patches = [
            mock.patch.object(cm, "load_cost_params", return_value={}),
            mock.patch.object(cm, "_symbol_vintages", return_value=VINTAGES),
            mock.patch.object(cm, "_front_month_vintages", return_value={}),
            mock.patch.object(cm, "_currency_vintages", return_value={}),
            mock.patch.object(cm, "_roll_for", return_value={}),
            mock.patch.object(cm, "_UNIVERSE_CACHE", dict(INDEX)),
            mock.patch.object(checks, "_INDEX_ROUTES", dict(INDEX)),
            mock.patch.dict(os.environ, {checks.ENV_SWITCH: "1"}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        if self.saved is None:
            pit_universe._cache.pop(self.key, None)
        else:
            pit_universe._cache[self.key] = self.saved

    def run_code(self, symbols, prices, init="pass", peek="pass", extra=""):
        if "sp500" in symbols:
            pit_universe._cache[self.key] = _universe(prices)
        code = RUN.substitute(symbols=repr(symbols), init=init, peek=peek, extra=extra)
        namespace = {"__name__": "__main__"}
        with offline(prices):
            exec(code, namespace)
        return namespace["strategy"]


class HealthyRun(_Harness):
    def test_a_point_in_time_book_passes_all_four(self):
        strategy = self.run_code(["sp500"], _prices())
        result = strategy.checks
        self.assertIs(result, strategy.run_report["checks"])
        items = _by_id(result)
        self.assertEqual([i["id"] for i in result["items"]], list(checks.CHECK_IDS))
        for check_id, item in items.items():
            self.assertEqual(item["status"], "pass", (check_id, item["summary"]))
        self.assertEqual(items["lookahead"]["summary"], "no future data read")
        self.assertEqual(items["universe"]["summary"],
                         "point-in-time sp500, 3 names, 1 delisted included")
        self.assertEqual(items["execution"]["summary"], "signal at close, fill at next open")
        self.assertTrue(items["costs"]["summary"].startswith(
            "3 of 3 traded names at measured spread (100% of traded value)"))
        self.assertEqual(items["lookahead"]["detail"]["sources"][0]["source"], "exec")

    def test_the_block_is_the_site_contract(self):
        result = self.run_code(["sp500"], _prices()).checks
        self.assertEqual(set(result), {"computedBy", "toolboxVersion", "computedAt", "items"})
        self.assertEqual(result["computedBy"], "harness")
        self.assertTrue(result["computedAt"].endswith("Z"))
        json.dumps(result, allow_nan=False)  # strict JSON: no NaN, no numpy
        for item in result["items"]:
            self.assertEqual(set(item), {"id", "status", "summary", "detail"})
            self.assertIn(item["status"], ("pass", "fail", "warn"))
            self.assertNotIn("\n", item["summary"])
            self.assertLess(len(item["summary"]), 200)

    def test_an_etf_list_is_not_a_survivor_list(self):
        strategy = self.run_code(["SPY", "TLT"], _prices(("SPY", "TLT")))
        item = _by_id(strategy.checks)["universe"]
        self.assertEqual(item["status"], "pass")
        self.assertEqual(item["summary"], "no single stocks: 2 etf")

    def test_switched_off_it_leaves_no_trace(self):
        with mock.patch.dict(os.environ, {checks.ENV_SWITCH: "0"}):
            strategy = self.run_code(["sp500"], _prices())
        self.assertFalse(hasattr(strategy, "checks"))
        self.assertNotIn("checks", strategy.run_report)


class FailingRuns(_Harness):
    def test_a_fixed_list_of_todays_stocks_warns(self):
        strategy = self.run_code(["A", "B"], _prices(("A", "B")))
        item = _by_id(strategy.checks)["universe"]
        self.assertEqual(item["status"], "warn")
        self.assertEqual(item["summary"],
                         "fixed list of 2 stocks over 6 years — today's names, survivorship bias")

    def test_reading_tomorrows_close_fails(self):
        strategy = self.run_code(
            ["sp500"], _prices(),
            peek="tomorrow = self.data.close[1] if len(self) < self.data.buflen() else None",
        )
        item = _by_id(strategy.checks)["lookahead"]
        self.assertEqual(item["status"], "fail")
        self.assertTrue(item["summary"].startswith("future data read: self.data.close[1] (line "))

    def test_cheat_on_close_fails(self):
        strategy = self.run_code(["sp500"], _prices(), init="self.broker.set_coc(True)")
        item = _by_id(strategy.checks)["execution"]
        self.assertEqual(item["status"], "fail")
        self.assertRegex(item["summary"], r"^\d+ of \d+ fills on their signal bar \(cheat-on-close\)$")
        self.assertEqual(item["detail"]["sameBarFills"], item["detail"]["fills"])

    def test_a_flat_commission_of_the_strategy_warns(self):
        strategy = self.run_code(["sp500"], _prices(), extra='broker_kwargs={"commission": 0.0005}')
        item = _by_id(strategy.checks)["costs"]
        self.assertEqual(item["status"], "warn")
        self.assertEqual(item["summary"],
                         "flat commission set by the strategy (5 bp) — measured spreads not applied")

    def test_the_0147_alias_defect_fails(self):
        """``["sp500"]`` judged as written: every member at the 1 bp floor, as 0.1.47 did."""

        def as_written(symbols):
            symbols = [symbols] if isinstance(symbols, str) else list(symbols)
            return cm.equity_symbols(symbols), cm.currency_symbols(symbols)

        with mock.patch.object(pwb_bt, "cost_classes", as_written):
            strategy = self.run_code(["sp500"], _prices())
        item = _by_id(strategy.checks)["costs"]
        self.assertEqual(item["status"], "fail")
        self.assertEqual(item["summary"],
                         "0 of 3 traded names at measured spread — default 1 bp on 100% of traded value")
        self.assertEqual(item["detail"]["unexplainedDefaultNames"], ["A", "B", "X"])

    def test_a_check_that_raises_is_a_warning_not_an_exception(self):
        with mock.patch.object(checks, "check_universe", side_effect=RuntimeError("boom")):
            strategy = self.run_code(["sp500"], _prices())
        self.assertTrue(strategy.log_data)
        item = _by_id(strategy.checks)["universe"]
        self.assertEqual(item["status"], "warn")
        self.assertEqual(item["summary"], "check could not run — RuntimeError: boom")
        self.assertEqual(_by_id(strategy.checks)["execution"]["status"], "pass")

    def test_a_failure_to_assemble_is_four_warnings(self):
        with mock.patch.object(checks, "compute", side_effect=RuntimeError("down")):
            strategy = self.run_code(["sp500"], _prices())
        result = strategy.checks
        self.assertEqual(set(result), {"computedBy", "toolboxVersion", "computedAt", "items"})
        self.assertEqual([i["status"] for i in result["items"]], ["warn"] * 4)
        self.assertEqual(result["items"][0]["summary"], "checks could not run — RuntimeError: down")


# --------------------------------------------------------------------------- #
# The rules on their own, at their thresholds
# --------------------------------------------------------------------------- #


def _facts(named, end, alias=None, members=0, delisted=0):
    return {"alias": alias, "frozen": False, "members": members, "delisted": delisted,
            "end": pd.Timestamp(end),
            "named": {k: {"class": c, "first": pd.Timestamp(f), "loaded": True}
                      for k, (c, f) in named.items()}}


class UniverseRule(unittest.TestCase):
    def test_the_span_threshold(self):
        under = checks.check_universe(_facts({"AAPL": ("stock", "2015-01-01")}, "2019-12-01"))
        over = checks.check_universe(_facts({"AAPL": ("stock", "2015-01-01")}, "2020-01-02"))
        self.assertEqual(under["status"], "pass")
        self.assertEqual(over["status"], "warn")
        self.assertEqual(over["summary"],
                         "fixed list of 1 stock over 5 years — today's names, survivorship bias")

    def test_a_crypto_basket_is_a_selection_a_coin_is_not(self):
        two = {"BTC": ("crypto", "2014-01-01"), "ETH": ("crypto", "2016-01-01")}
        three = {**two, "LTC": ("crypto", "2014-01-01")}
        self.assertEqual(checks.check_universe(_facts(two, "2025-01-01"))["status"], "pass")
        self.assertEqual(checks.check_universe(_facts(three, "2025-01-01"))["status"], "warn")

    def test_a_point_in_time_alias_with_a_stock_beside_it_warns(self):
        item = checks.check_universe(
            _facts({"AAPL": ("stock", "2000-01-01")}, "2025-01-01", "sp500", 1900, 600)
        )
        self.assertEqual(item["status"], "warn")
        self.assertTrue(item["summary"].startswith(
            "point-in-time sp500, 1900 names, 600 delisted included; plus fixed list of 1 stock"))

    def test_indices_and_currencies_pass(self):
        item = checks.check_universe(_facts(
            {"SPX": ("index", "1990-01-01"), "EURUSD": ("forex", "1990-01-01")}, "2025-01-01"))
        self.assertEqual(item["status"], "pass")


def _journal(values, same=0):
    return {"fills": len(values) * 4, "same_bar": same, "unmatched": 0, "examples": [],
            "exectypes": {"Market": len(values) * 4},
            "by_symbol": {k: {"fills": 4, "value": v, "comm": v * 1e-4} for k, v in values.items()}}


_Cost = namedtuple("_Cost", "symbol half_spread source year")


class _Scheme:
    def __init__(self, source):
        self.pwb_cost = _Cost("?", 1e-4 if source == "default" else 5e-4, source, 2020)


class CostsRule(unittest.TestCase):
    ROUTES = {"A": "Stocks-Daily-Price", "B": "Stocks-Daily-Price", "SPX": "Indices-Daily-Price"}

    def _costs(self, share):
        values = {"A": 1.0 - share, "B": share}
        schemes = {"A": _Scheme("measured"), "B": _Scheme("default")}
        return checks.check_costs(_journal(values), schemes, {"mode": "measured", "calls": []},
                                  routes=self.ROUTES)

    def test_the_thresholds(self):
        self.assertEqual(self._costs(0.04)["status"], "pass")
        self.assertEqual(self._costs(0.06)["status"], "warn")
        self.assertEqual(self._costs(0.19)["status"], "warn")
        self.assertEqual(self._costs(0.21)["status"], "fail")

    def test_an_index_at_the_floor_is_explained(self):
        item = checks.check_costs(
            _journal({"A": 0.5, "SPX": 0.5}), {"A": _Scheme("measured"), "SPX": _Scheme("default")},
            {"mode": "measured", "calls": []}, routes=self.ROUTES,
        )
        self.assertEqual(item["status"], "pass")
        self.assertEqual(item["summary"], "1 of 2 traded names at measured spread (50% of traded "
                                          "value); 1 at the floor (index: no cost table)")

    def test_a_strategy_commission_that_raises_the_fee_warns(self):
        policy = {"mode": "higher_of_measured_and_strategy", "floor_perc": 0.001, "floor_fixed": 0.0,
                  "raised_symbols": 1, "calls": [{"name": None, "kind": "perc", "value": 0.001}]}
        item = checks.check_costs(_journal({"A": 1.0}), {"A": _Scheme("measured")}, policy,
                                  routes=self.ROUTES)
        self.assertEqual(item["status"], "warn")
        self.assertIn("the strategy sets its own commission (10 bp)", item["summary"])


class ExecutionRule(unittest.TestCase):
    def test_one_fill_on_its_signal_bar_fails(self):
        journal = _journal({"A": 1.0}, same=1)
        self.assertEqual(checks.check_execution(journal, {"coc": False})["status"], "fail")
        journal["same_bar"] = 0
        self.assertEqual(checks.check_execution(journal, {"coc": False})["status"], "pass")

    def test_nothing_filled_is_a_warning(self):
        journal = _journal({})
        self.assertEqual(checks.check_execution(journal, {})["status"], "warn")


class Version(unittest.TestCase):
    def test_the_reported_version_is_the_release(self):
        import configparser
        import pwb_toolbox

        setup = configparser.ConfigParser()
        setup.read(os.path.join(os.path.dirname(__file__), "..", "setup.cfg"))
        self.assertEqual(pwb_toolbox.__version__, setup["metadata"]["version"])
        self.assertEqual(checks.toolbox_version(), pwb_toolbox.__version__)


if __name__ == "__main__":
    unittest.main()
