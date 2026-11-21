"""``run_strategy(short_borrow_bps=...)``: what a short leg pays to borrow its shares.

At 0 -- the default, and without the argument -- the NAV must be the one the
harness produced before the parameter existed, bit for bit: the reference in
``tests/data/short_borrow_nav_reference.json`` was written by ``origin/main``
(a0c8b06, PR #81) on the books of ``_long_short_book.py``.
"""

import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be
from pwb_toolbox.backtesting import checks

import _long_short_book as book
import test_pit_hold_accounting as acc
from _synthetic import offline, panel

REFERENCE = json.loads(
    (Path(__file__).parent / "data" / "short_borrow_nav_reference.json").read_text()
)


def _hex(values):
    return [float(v).hex() for v in values]


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class ZeroIsBitIdentical(unittest.TestCase):
    def test_plain_book_without_the_argument(self):
        strategy = _quiet(book.run_book)
        self.assertEqual(_hex(book.nav(strategy)), REFERENCE["plain"])
        self.assertEqual(strategy.borrow_cost, 0.0)
        self.assertFalse(strategy._pwb_borrow_added)

    def test_plain_book_at_zero(self):
        for bps in (0, 0.0):
            strategy = _quiet(book.run_book, short_borrow_bps=bps)
            self.assertEqual(_hex(book.nav(strategy)), REFERENCE["plain"])
            self.assertEqual(strategy.run_report["borrow"]["total"], 0.0)

    def test_environment_at_zero(self):
        with mock.patch.dict(os.environ, {"PWB_SHORT_BORROW_BPS": "0"}):
            strategy = _quiet(book.run_book)
        self.assertEqual(_hex(book.nav(strategy)), REFERENCE["plain"])

    def test_hold_book_short_outside_the_universe(self):
        case = type("Case", (acc._Base,), {"runTest": lambda self: None})()
        case.setUp()
        try:
            for kwargs in ({}, {"short_borrow_bps": 0.0}):
                with mock.patch.object(be, "run_strategy", _with(be.run_strategy, kwargs)):
                    strategy = _quiet(case._run, acc.ShortX)
                self.assertTrue(strategy._pwb_ms_added)  # the marks went through the cash
                self.assertEqual(_hex(book.nav(strategy)), REFERENCE["hold_short"])
        finally:
            case.tearDown()

    def test_borrow_changes_the_nav(self):
        strategy = _quiet(book.run_book, short_borrow_bps=100)
        nav = book.nav(strategy)
        ref = [float.fromhex(v) for v in REFERENCE["plain"]]
        self.assertLess(nav[-1], ref[-1])
        self.assertGreater(strategy.borrow_cost, 0.0)

    def test_negative_is_refused(self):
        with self.assertRaises(ValueError):
            book.run_book(short_borrow_bps=-1)


def _with(fn, extra):
    def call(*args, **kwargs):
        return fn(*args, **{**kwargs, **extra})

    return call


N = 40
SHARES = 100
PRICE = 100.0
OPEN_BAR = 5  # the order is placed on bar 4 and filled at the open of bar 5


class ShortOnce(BaseStrategy):
    """Short 100 shares of a name that never moves, on bar 4; long a moving one."""

    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True

    def next(self):
        super().next()
        if len(self) - 1 == OPEN_BAR - 1:
            self.sell(self.getdatabyname("S"), size=SHARES)
            self.buy(self.getdatabyname("L"), size=SHARES)


def _short_once(bps):
    rng = np.random.default_rng(2)
    prices = panel({
        "S": np.full(N, PRICE),
        "L": PRICE * np.exp(np.cumsum(rng.normal(0, 0.01, N))),
    })
    with offline(prices):
        strategy = _quiet(
            be.run_strategy,
            indicator_cls=None, indicator_kwargs={}, strategy_cls=ShortOnce,
            strategy_kwargs={}, symbols=["S", "L"], start_date="2020-01-01",
            cash=100_000.0, broker_kwargs={"commission": 0.0}, short_borrow_bps=bps,
        )
    return strategy, prices.index


class HandComputedCharge(unittest.TestCase):
    def test_constant_short_pays_act_365(self):
        bps = 250.0
        strategy, days = _short_once(bps)
        self.assertEqual(strategy.getposition(strategy.getdatabyname("S")).size, -SHARES)
        value = SHARES * PRICE
        held = (days[-1] - days[OPEN_BAR]).days  # calendar days from the fill's close to the last bar
        expected = value * bps / 1e4 * held / 365
        self.assertAlmostEqual(strategy.borrow_cost, expected, places=9)
        report = strategy.run_report["borrow"]
        self.assertAlmostEqual(report["total"], expected, places=9)
        self.assertEqual(report["short_borrow_bps"], bps)
        self.assertEqual(report["bars"], N - 1 - OPEN_BAR)
        self.assertEqual(report["short_names"], 1)
        self.assertAlmostEqual(report["start_nav_share"], expected / 100_000.0, places=12)
        # The last bar's charge (3 days over a weekend or 1) is booked, not in the NAV.
        last = value * bps / 1e4 * (days[-1] - days[-2]).days / 365
        self.assertAlmostEqual(report["pending_at_end"], last, places=9)
        free, _ = _short_once(0.0)
        drop = book.nav(free)[-1] - book.nav(strategy)[-1]
        self.assertAlmostEqual(drop, expected - last, places=6)

    def test_printed_line(self):
        rng = np.random.default_rng(2)
        prices = panel({"S": np.full(N, PRICE), "L": PRICE * np.exp(np.cumsum(rng.normal(0, 0.01, N)))})
        out = io.StringIO()
        with offline(prices), contextlib.redirect_stdout(out):
            be.run_strategy(
                indicator_cls=None, indicator_kwargs={}, strategy_cls=ShortOnce,
                strategy_kwargs={}, symbols=["S", "L"], start_date="2020-01-01",
                cash=100_000.0, broker_kwargs={"commission": 0.0}, short_borrow_bps=250,
            )
        line = next(l for l in out.getvalue().splitlines() if l.startswith("Short borrow: "))
        payload = json.loads(line[len("Short borrow: "):])
        self.assertEqual(payload["short_borrow_bps"], 250.0)
        self.assertEqual(payload["short_names"], 1)
        self.assertGreater(payload["total"], 0)

    def test_environment_sets_the_default(self):
        with mock.patch.dict(os.environ, {"PWB_SHORT_BORROW_BPS": "250"}):
            from_env, _ = _short_once(None)
        explicit, _ = _short_once(250.0)
        self.assertEqual(from_env.borrow_cost, explicit.borrow_cost)
        self.assertEqual(_hex(book.nav(from_env)), _hex(book.nav(explicit)))

    def test_funding_audit_counts_the_pending_charge(self):
        strategy, _ = _short_once(250.0)
        self.assertTrue(strategy._pwb_borrow_added)
        # the last charge is still in the broker's queue, which the audit adds
        pending = be._pending_cash(strategy.broker)
        self.assertAlmostEqual(-pending, strategy.run_report["borrow"]["pending_at_end"], places=9)
        free, _ = _short_once(0.0)
        self.assertFalse(free._pwb_borrow_added)
        self.assertEqual(be._pending_cash(free.broker), 0.0)


class CostsCheck(unittest.TestCase):
    def test_run_reports_the_borrow(self):
        strategy = _quiet(book.run_book, short_borrow_bps=75)
        item = next(i for i in strategy.checks["items"] if i["id"] == "costs")
        self.assertEqual(item["detail"]["shortBorrowBps"], 75.0)
        self.assertAlmostEqual(item["detail"]["shortBorrowCost"], strategy.borrow_cost)
        self.assertIn("short borrow 75 bp/yr", item["summary"])

    def test_run_at_zero_says_so(self):
        strategy = _quiet(book.run_book)
        item = next(i for i in strategy.checks["items"] if i["id"] == "costs")
        self.assertIn(checks.COSTS_NO_BORROW, item["summary"])
        self.assertEqual(item["detail"]["shortBorrowBps"], 0.0)
        self.assertEqual(item["status"], "warn")  # flat commission: warn already

    def _measured(self, borrow):
        journal = {"by_symbol": {"A": {"value": 1_000.0, "comm": 0.5}}}
        cost = SimpleNamespace(source="measured", half_spread=0.0005)
        schemes = {"A": SimpleNamespace(pwb_cost=cost)}
        return checks.check_costs(journal, schemes, {"mode": "measured"}, borrow=borrow)

    def test_pass_becomes_warn_when_shorts_pay_nothing(self):
        self.assertEqual(self._measured(None)["status"], "pass")
        long_only = {"short_names": 0, "short_borrow_bps": 0.0, "total": 0.0}
        self.assertEqual(self._measured(long_only)["status"], "pass")
        self.assertNotIn("shortBorrowBps", self._measured(long_only)["detail"])
        free = {"short_names": 3, "short_borrow_bps": 0.0, "total": 0.0, "start_nav_share": 0.0}
        item = self._measured(free)
        self.assertEqual(item["status"], "warn")
        self.assertTrue(item["summary"].endswith("; short leg carries no borrow cost"))
        paid = {"short_names": 3, "short_borrow_bps": 50.0, "total": 1234.0, "start_nav_share": 0.01}
        item = self._measured(paid)
        self.assertEqual(item["status"], "pass")
        self.assertEqual(item["detail"]["shortBorrowCost"], 1234.0)
        self.assertIn("short borrow 50 bp/yr (1,234 paid)", item["summary"])


if __name__ == "__main__":
    unittest.main()
