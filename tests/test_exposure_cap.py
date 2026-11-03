"""The exposure cap scales what a book cannot fund, bar by bar, and nothing else.

Each scenario reproduces one defect of the 0.1.31-0.1.42 cap (shrunken-books
investigation, 2026-11-03) and fails on that code:

* stale targets -- ``close()`` never cleared a name's target, so the
  "requested gross" summed every name ever held (4.9 for a ~1 book);
* the cap was 0.99 over the peak of the whole run, so a book that levers up
  for a few weeks was shrunk on every other bar too;
* a debit of a few dollars, or a book sized only by ``order_target_size``,
  re-ran the whole backtest for nothing;
* a dollar-neutral book at gross 2 was halved when a single order was refused.

The two hand-computed books pin the behaviour PR #43 asked for: a 100 % book
plus commission is funded at 99 % instead of seeing its orders refused.
"""

import unittest

import backtrader as bt
import numpy as np
import pandas as pd

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be

from _synthetic import offline, panel


class _Harnessed(BaseStrategy):
    """What ``run_strategy`` expects of a strategy class."""

    params = (("indicator_cls", None), ("indicator_kwargs", {}))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True


def _run(prices, strategy_cls, commission=0.0, symbols=("A",), **kwargs):
    with offline(prices):
        return be.run_strategy(
            indicator_cls=None,
            indicator_kwargs={},
            strategy_cls=strategy_cls,
            strategy_kwargs={},
            symbols=list(symbols),
            start_date="2020-01-01",
            cash=100_000.0,
            broker_kwargs={"commission": commission},
            **kwargs,
        )


class Rotation(bt.Strategy):
    """``toy_cap.py``: two names at 49 % every 20 bars, the rest exited by close()."""

    params = (("use_close", True),)

    def next(self):
        i = len(self)
        if i % 20 == 1:
            k = (i // 20) % 10
            for j, d in enumerate(self.datas):
                if j in (k, (k + 1) % 10):
                    self.order_target_percent(d, 0.49)
                elif self.getposition(d).size:
                    if self.p.use_close:
                        self.close(d)
                    else:
                        self.order_target_percent(d, 0.0)


class StaleTargetsTest(unittest.TestCase):
    def _requested(self, use_close):
        idx = pd.bdate_range("2020-01-01", periods=200)
        cerebro = bt.Cerebro(stdstats=False)
        rng = np.random.default_rng(0)
        for j in range(10):
            p = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
            frame = pd.DataFrame({"open": p, "high": p, "low": p, "close": p}, index=idx)
            cerebro.adddata(bt.feeds.PandasData(dataname=frame), name=f"S{j}")
        cerebro.addstrategy(be._with_exposure_cap(Rotation, 1.0), use_close=use_close)
        cerebro.broker.set_cash(100_000)
        return cerebro.run()[0].requested_gross

    def test_close_clears_the_target(self):
        # 0.1.41: 4.90 -- every name ever held still counted
        self.assertAlmostEqual(self._requested(use_close=True), 0.98, places=6)

    def test_target_zero_clears_the_target(self):
        self.assertAlmostEqual(self._requested(use_close=False), 0.98, places=6)


class VariableLeverage(_Harnessed):
    """A managed-volatility book: 50 % most of the time, 200 % for 40 bars."""

    def next(self):
        super().next()
        i = len(self)
        self.order_target_percent(self.data0, 2.0 if 100 <= i < 140 else 0.5)
        self.exposure = getattr(self, "exposure", {})
        value = self.broker.getvalue()
        self.exposure[i] = self.getposition(self.data0).size * self.data0.close[0] / value


class PeakLeverageTest(unittest.TestCase):
    def test_low_leverage_bars_are_not_shrunk_by_the_peak(self):
        close = 100 * np.exp(np.cumsum(np.full(300, 0.0004)))
        strategy = _run(panel({"A": close}), VariableLeverage)
        # 0.1.41: every bar at 0.99 / 2.0 of its target, 0.2475 instead of 0.5
        self.assertAlmostEqual(strategy.exposure[60], 0.5, delta=0.01)
        self.assertAlmostEqual(strategy.exposure[250], 0.5, delta=0.01)
        # the 200 % bars are funded at 99 %, not refused
        self.assertAlmostEqual(strategy.exposure[130], 0.99, delta=0.01)
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertAlmostEqual(strategy.exposure_cap, 0.495, places=6)
        self.assertEqual(strategy.run_report["scaled_bars"], 40)
        self.assertAlmostEqual(strategy.requested_long, 2.0)


    def test_uniform_scaling_keeps_the_shape_of_the_leverage(self):
        close = 100 * np.exp(np.cumsum(np.full(300, 0.0004)))
        strategy = _run(panel({"A": close}), VariableLeverage, scaling="uniform")
        # every bar divided by the peak: 0.5 x 0.495 and 2.0 x 0.495
        self.assertAlmostEqual(strategy.exposure[60], 0.2475, delta=0.01)
        self.assertAlmostEqual(strategy.exposure[130], 0.99, delta=0.01)
        self.assertAlmostEqual(strategy.exposure_cap, 0.495, places=6)
        self.assertEqual(strategy.funding_audit["margin"], 0)

    def test_leverage_above_the_account_is_refused_up_front(self):
        with self.assertRaises(ValueError):
            _run(panel({"A": np.full(10, 100.0)}), VariableLeverage, max_leverage=2.0)

class Cohorts(_Harnessed):
    """slow_capital...: a cohort at 100 % every bar, held ``hold`` bars after its fill.

    Each bar buys five names not already held, at 20 % each, and exits the
    cohort it filled ``hold`` bars ago with a target of zero -- the exits
    submitted before the entries, as in the published strategy. With
    ``hold=1`` two cohorts are held at every close: the book asks for 200 %.
    """

    params = (("hold", 1),)

    def __init__(self):
        super().__init__()
        self.entry = {}
        self.exposure = []

    def next(self):
        super().next()
        now = len(self)
        value = self.broker.getvalue()
        self.exposure.append(
            sum(self.getposition(d).size * d.close[0] for d in self.datas) / value
        )
        for d in self.datas:
            if not self.getposition(d).size:
                self.entry.pop(d._name, None)
                continue
            entered = self.entry.setdefault(d._name, now)
            if now - entered >= self.p.hold:
                self.order_target_percent(d, 0.0)
                del self.entry[d._name]
        picks = [self.datas[(now * 5 + j) % len(self.datas)] for j in range(5)]
        picks = [d for d in picks if not self.getposition(d).size]
        for d in picks:
            self.order_target_percent(d, 1.0 / len(picks))
            self.entry[d._name] = now + 1


def _cohorts(hold):
    class Book(Cohorts):
        params = (("hold", hold),)

    rng = np.random.default_rng(0)
    close = {
        f"S{j}": 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, 300))) for j in range(20)
    }
    return _run(panel(close), Book, commission=0.001, symbols=tuple(close))


class CarriedPositionsTest(unittest.TestCase):
    """A book that does not re-target what it holds is scaled as one book.

    As published every other cohort is refused, so the bars after a refusal
    read 100 % and the bar schedule sent their cohort at 99 %; the next
    cohort, scaled for 200 %, then found the account full. 0.1.43 stepped the
    whole schedule down until the refusals fell under 2 % (exposure cap
    0.325, 6 runs; 59 % and Sharpe 0.019 on the published strategy).
    """

    def test_two_overlapping_cohorts_are_funded_at_99_percent(self):
        strategy = _cohorts(hold=1)
        report = strategy.run_report
        self.assertAlmostEqual(strategy.requested_long, 2.0, places=3)
        self.assertAlmostEqual(strategy.exposure_cap, 0.99 / 2.0, places=3)
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertAlmostEqual(float(np.median(strategy.exposure[10:])), 0.99, delta=0.01)
        # as published, the bar schedule, one step at 90 %, then one scale
        self.assertEqual(report["attempts"], 4)
        self.assertEqual(report["scaling_used"], "uniform")

    def test_a_cohort_the_refusals_hid_is_measured_on_the_funded_run(self):
        # three cohorts held at each close; as published the third was always
        # refused, so the book read 200 %, not 300 %
        strategy = _cohorts(hold=2)
        self.assertAlmostEqual(strategy.requested_long, 2.0, places=3)
        self.assertAlmostEqual(strategy.exposure_cap, 0.99 / 3.0, delta=0.005)
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertAlmostEqual(float(np.median(strategy.exposure[10:])), 0.99, delta=0.015)


class UnderfundedTriggerTest(unittest.TestCase):
    def _audit(self, min_cash, ratio):
        return {
            "margin": 0,
            "submitted": 100,
            "reject_rate": 0.0,
            "min_cash": min_cash,
            "min_cash_ratio": ratio,
            "min_value": 100_000.0,
        }

    def test_a_one_dollar_debit_is_not_underfunded(self):
        # 0.1.41: any min_cash < 0 re-ran the whole backtest smaller
        self.assertFalse(be._underfunded(self._audit(-1.0, -1e-5), 0.02))

    def test_a_real_debit_is(self):
        self.assertTrue(be._underfunded(self._audit(-5_000.0, -0.05), 0.02))


class SizeOnly(_Harnessed):
    """Asks for more shares than the account holds, by order_target_size only."""

    runs = 0

    def __init__(self):
        super().__init__()
        SizeOnly.runs += 1

    def next(self):
        super().next()
        if len(self) % 5 == 1:
            self.order_target_size(self.data0, 2_000 if len(self) % 10 == 1 else 0)


class NothingToScaleTest(unittest.TestCase):
    def test_a_book_without_targets_is_not_rerun(self):
        SizeOnly.runs = 0
        strategy = _run(panel({"A": np.full(60, 100.0)}), SizeOnly)
        # 0.1.41: six runs, each scaling targets the strategy never set
        self.assertEqual(SizeOnly.runs, 1)
        self.assertGreater(strategy.funding_audit["margin"], 0)
        self.assertEqual(strategy.run_report["attempts"], 1)


class BuyAndHold(_Harnessed):
    """Targets once on the first bar, then holds."""

    params = (("weights", {}),)

    def next(self):
        super().next()
        if len(self) == 1:
            for name, weight in self.p.weights.items():
                self.order_target_percent(self.getdatabyname(name), weight)


def _book(weights, commission):
    class Book(BuyAndHold):
        params = (("weights", weights),)

    close = {
        "A": np.r_[100.0, 100.0, np.full(8, 110.0)],
        "B": np.r_[100.0, 100.0, np.full(8, 90.0)],
    }
    return _run(panel(close), Book, commission=commission, symbols=("A", "B"))


class HandComputedNavTest(unittest.TestCase):
    """NAVs checked against arithmetic, not against another run."""

    def test_long_only_at_100_percent_is_funded_at_99(self):
        strategy = _book({"A": 0.5, "B": 0.5}, commission=0.001)
        # 0.495 x 100 000 / 100 = 495 shares each, bought at 100 plus 0.1 %
        shares = 495
        cash = 100_000 - 2 * shares * 100 * 1.001
        expected = cash + shares * 110 + shares * 90
        self.assertAlmostEqual(strategy.log_data[-1]["value"], expected, places=6)
        self.assertEqual(strategy.funding_audit["margin"], 0)
        self.assertEqual(strategy.run_report["attempts"], 2)

    def test_long_short_at_gross_2_keeps_both_legs_at_99(self):
        # The long leg is submitted first and refused (cash 100 000 < 100 100).
        # Scaling the long side to 99 % funds it whatever the order; 0.1.41
        # scaled the gross to 99 % instead and halved the book (495 shares).
        strategy = _book({"A": 1.0, "B": -1.0}, commission=0.001)
        shares = 990
        cash = 100_000 - shares * 100 * 1.001 + shares * 100 * 0.999
        expected = cash + shares * 110 - shares * 90
        self.assertAlmostEqual(strategy.log_data[-1]["value"], expected, places=6)
        self.assertEqual(strategy.funding_audit["margin"], 0)

    def test_long_short_that_is_funded_is_left_alone(self):
        # Short leg first, no commission: fundable as published, never scaled.
        strategy = _book({"B": -1.0, "A": 1.0}, commission=0.0)
        expected = 100_000 + 1_000 * 10 + 1_000 * 10
        self.assertAlmostEqual(strategy.log_data[-1]["value"], expected, places=6)
        self.assertEqual(strategy.exposure_cap, 1.0)
        self.assertEqual(strategy.run_report["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
