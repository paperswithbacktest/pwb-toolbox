"""One strategy file, two engines, the same NAV to the last bit.

The strategy below is written the way ~150 corpus strategies are: it names
``backtrader`` itself (``import backtrader as bt``) next to ``BaseStrategy``. It
runs through ``python -m pwb.engine --engine NAME --report``, which is
how a campaign switches engine without touching a strategy: on Tradewind the
name ``backtrader`` resolves to Tradewind and no module of a backtrader package
may be loaded.

Two price sets:

* on a dyadic grid (prices in 1/64, half-spreads in 1/2048), every sum the
  engines form is exact, so the order in which they add the positions cannot
  show: the NAV paths must be **equal as floats** (``==`` on every bar, same
  ``float.hex``), and so must cash and positions;
* on arbitrary float prices the same paths agree to the last bit or one unit
  in the last place: Tradewind's spec/02 records that residual (row "The marked
  value is cash + t": a few marks in a hundred differ in their last bit, cash
  identical), so this test bounds it instead of hiding it.

Synthetic bars, no download, a few seconds. Skipped unless both engines are
importable by this interpreter.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from pwb import engine

BOTH = bool(importlib.util.find_spec("backtrader") and importlib.util.find_spec("tradewind"))

STRATEGY = textwrap.dedent(
    r'''
    import json
    import os
    import sys

    import backtrader as bt
    import numpy as np
    import pandas as pd

    import pwb.backtesting as pwb_bt
    from pwb.backtesting.feeds import ArrayPandasData

    GRID = os.environ.get("GRID") == "1"
    rng = np.random.default_rng(11)
    index = pd.bdate_range("2018-01-02", periods=400)
    frames = {}
    for i in range(4):
        close = 25 * np.exp(np.cumsum(rng.normal(0.0002, 0.015, len(index))))
        openp = close * (1 + rng.normal(0, 0.004, len(index)))
        if GRID:
            close, openp = np.round(close * 64) / 64, np.round(openp * 64) / 64
        frames[f"A{i}"] = pd.DataFrame({
            "open": openp, "high": np.maximum(openp, close) + 0.25,
            "low": np.minimum(openp, close) - 0.25, "close": close,
            "volume": 2e5}, index=index)


    class Rotation(pwb_bt.BaseStrategy):
        params = (("lookback", 30), ("top", 2))

        def __init__(self):
            super().__init__()
            self.mom = {d._name: bt.indicators.RateOfChange(d.close, period=self.p.lookback)
                        for d in self.datas}
            self.sma = {d._name: bt.indicators.SMA(d.close, period=15) for d in self.datas}

        def next(self):
            super().next()
            if len(self) % 10:
                return
            ranked = sorted(self.datas, key=lambda d: self.mom[d._name][0], reverse=True)
            winners = [d for d in ranked[: self.p.top] if d.close[0] > self.sma[d._name][0]]
            for d in self.datas:
                self.order_target_percent(d, target=0.45 if d in winners else 0.0)


    cerebro = bt.Cerebro(stdstats=False)
    feeds = {}
    for name, frame in frames.items():
        feeds[name] = ArrayPandasData(dataname=frame)
        cerebro.adddata(feeds[name], name=name)
    cerebro.addstrategy(Rotation, total_days=len(index))
    cerebro.broker.set_cash(100_000)
    for k, name in enumerate(frames):
        cerebro.broker.addcommissioninfo(
            pwb_bt.SpreadImpactCommission(half_spread=(k + 1) / 2048, data=feeds[name]),
            name=name,
        )
    strat = cerebro.run()[0]
    nav = [row["value"] for row in strat.log_data]
    sys.stdout.write("RESULT " + json.dumps({
        "engine": pwb_bt.engine_name(),
        "bt": bt.__name__,
        "dates": [row["date"] for row in strat.log_data],
        "nav": nav,
        "hex": [float(v).hex() for v in nav],
        "cash": float(cerebro.broker.getcash()).hex(),
        "positions": strat.get_latest_positions(),
    }) + "\n")
    '''
)


def _run(engine_name, script, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != engine.ENV_VAR}
    env.update(TQDM_DISABLE="1", **(extra_env or {}))
    proc = subprocess.run(
        [sys.executable, "-m", "pwb.engine", "--engine", engine_name, "--report", script],
        env=env, capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        tail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else proc.stdout
        raise AssertionError(f"{engine_name}: {tail}")
    lines = proc.stdout.splitlines()
    result = json.loads(next(l for l in lines if l.startswith("RESULT "))[len("RESULT "):])
    report = next(l for l in lines if l.startswith("ENGINE "))
    return result, report


@unittest.skipUnless(BOTH, "both engines are needed")
class SameNavToTheBitTest(unittest.TestCase):
    GRID = "1"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.script = os.path.join(cls.tmp.name, "strategy.py")
        with open(cls.script, "w", encoding="utf-8") as fh:
            fh.write(STRATEGY)
        cls.bt_result, cls.bt_report = _run("backtrader", cls.script, {"GRID": cls.GRID})
        cls.tw_result, cls.tw_report = _run("tradewind", cls.script, {"GRID": cls.GRID})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_run_is_on_the_engine_it_asked_for(self):
        self.assertEqual(self.bt_result["engine"], "backtrader")
        self.assertEqual(self.bt_result["bt"], "backtrader")
        self.assertEqual(self.tw_result["engine"], "tradewind")
        # ``import backtrader as bt`` in the strategy gave Tradewind ...
        self.assertEqual(self.tw_result["bt"], "tradewind")
        # ... and nothing was loaded from a backtrader package.
        self.assertIn("toolbox=tradewind backtrader_name=engine", self.tw_report)
        self.assertIn("leaked_backtrader_modules=0", self.tw_report)
        self.assertIn("toolbox=backtrader", self.bt_report)

    def test_nav_paths_are_bit_identical(self):
        ref, cand = self.bt_result, self.tw_result
        self.assertEqual(ref["dates"], cand["dates"])
        self.assertGreater(len(ref["nav"]), 300)
        self.assertNotEqual(ref["nav"][0], ref["nav"][-1], "the strategy never traded")
        self.assertEqual(ref["nav"], cand["nav"])
        self.assertEqual(ref["hex"], cand["hex"])
        self.assertEqual(ref["cash"], cand["cash"])
        self.assertEqual(ref["positions"], cand["positions"])


@unittest.skipUnless(BOTH, "both engines are needed")
class SameNavOnFloatPricesTest(SameNavToTheBitTest):
    """Arbitrary float prices: the same path to one unit in the last place."""

    GRID = "0"

    def test_nav_paths_are_bit_identical(self):
        ref, cand = self.bt_result, self.tw_result
        self.assertEqual(ref["dates"], cand["dates"])
        self.assertEqual(ref["cash"], cand["cash"])
        self.assertEqual(ref["positions"], cand["positions"])
        worst = max(abs(a - b) / abs(a) for a, b in zip(ref["nav"], cand["nav"]))
        self.assertLessEqual(worst, 4.5e-16, "more than one unit in the last place")
        same = sum(a == b for a, b in zip(ref["nav"], cand["nav"]))
        self.assertGreater(same / len(ref["nav"]), 0.8, f"only {same} marks bit for bit")


def _subprocess(code, engine_name):
    env = {k: v for k, v in os.environ.items() if k != engine.ENV_VAR}
    env[engine.ENV_VAR] = engine_name
    return subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )


class AliasAndCheckTest(unittest.TestCase):
    @unittest.skipUnless(BOTH, "both engines are needed")
    def test_alias_is_refused_once_the_real_backtrader_is_loaded(self):
        proc = _subprocess(
            "import backtrader, pwb.engine as e\n"
            "try:\n    e.use('tradewind')\nexcept RuntimeError as exc:\n    print('refused', exc)\n",
            "tradewind",
        )
        self.assertIn("refused", proc.stdout, proc.stderr)

    @unittest.skipUnless(importlib.util.find_spec("tradewind"), "tradewind not installed")
    def test_alias_gives_the_submodules_the_corpus_imports(self):
        proc = _subprocess(
            "import pwb.engine as e\n"
            "bt = e.use('tradewind')\n"
            "import backtrader, backtrader.feeds, backtrader.indicators as btind\n"
            "from backtrader.utils.date import num2date\n"
            "from backtrader.feeds import PandasData\n"
            "import pwb.backtesting as b\n"
            "assert backtrader is bt and btind is bt.indicators and PandasData is bt.PandasData\n"
            "assert num2date is bt.num2date and b.bt is bt\n"
            "assert b.BaseStrategy.__mro__[1].__module__.split('.')[0] == 'tradewind'\n"
            "print('ok')\n",
            "tradewind",
        )
        self.assertEqual(proc.stdout.strip(), "ok", proc.stderr)

    @unittest.skipUnless(importlib.util.find_spec("backtrader"), "backtrader not installed")
    def test_alias_is_a_no_op_on_backtrader(self):
        proc = _subprocess(
            "import sys, pwb.engine as e\n"
            "bt = e.use()\n"
            "import backtrader\n"
            "print(bt is backtrader, 'tradewind' in sys.modules)\n",
            "backtrader",
        )
        self.assertEqual(proc.stdout.strip(), "True False", proc.stderr)

    @unittest.skipUnless(importlib.util.find_spec("backtrader"), "backtrader not installed")
    def test_run_strategy_refuses_the_engine_it_is_not_on(self):
        proc = _subprocess(
            "import pwb.backtesting as b\n"
            "try:\n"
            "    b.run_strategy(None, {}, None, {}, [], '2020-01-01', 1, engine='tradewind')\n"
            "except RuntimeError as exc:\n"
            "    print('refused:', exc)\n",
            "backtrader",
        )
        self.assertIn("refused: this process runs on 'backtrader', not 'tradewind'", proc.stdout,
                      proc.stderr)

    def test_check_accepts_the_engine_in_force(self):
        self.assertEqual(engine.check(None), engine.name())
        self.assertEqual(engine.check(engine.name().upper()), engine.name())
        with self.assertRaises(ValueError):
            engine.check("zipline")


if __name__ == "__main__":
    unittest.main()
