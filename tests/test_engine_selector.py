"""The engine is chosen once, before the backtesting package binds to it.

Every case that binds the package runs in a subprocess, because a bound package
cannot be unbound: ``BaseStrategy`` is a subclass of the chosen engine's
``Strategy`` from the moment ``pwb_toolbox.backtesting`` is imported.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

from pwb_toolbox import engine

ENV = engine.ENV_VAR


def _installed(name):
    return importlib.util.find_spec(name) is not None


def _run(code, engine_name=None):
    env = {k: v for k, v in os.environ.items() if k != ENV}
    if engine_name is not None:
        env[ENV] = engine_name
    proc = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )
    if proc.returncode:
        raise AssertionError(proc.stderr.strip().splitlines()[-1] if proc.stderr else proc.stdout)
    return proc.stdout.strip()


REPORT = (
    "import sys, pwb_toolbox.backtesting as b; "
    "print(b.engine_name(), b.bt.__name__, b.BaseStrategy.__mro__[1].__module__.split('.')[0], "
    "'backtrader' in sys.modules, 'tradewind' in sys.modules)"
)


class EngineSelectorTest(unittest.TestCase):
    def test_names_are_validated(self):
        with self.assertRaises(ValueError):
            engine.select("zipline")
        self.assertEqual(engine._normalise(" Tradewind "), "tradewind")
        self.assertIn(engine.name(), engine.ENGINES)

    @unittest.skipUnless(_installed("backtrader"), "backtrader not installed")
    def test_default_is_backtrader_and_tradewind_stays_unimported(self):
        self.assertEqual(_run(REPORT), "backtrader backtrader backtrader True False")

    @unittest.skipUnless(_installed("tradewind"), "tradewind not installed")
    def test_environment_picks_tradewind_without_importing_backtrader(self):
        self.assertEqual(
            _run(REPORT, "tradewind"), "tradewind tradewind tradewind False True"
        )

    @unittest.skipUnless(_installed("tradewind"), "tradewind not installed")
    def test_select_before_import_wins_over_the_default(self):
        code = "import pwb_toolbox.engine as e; e.select('tradewind'); " + REPORT
        self.assertEqual(_run(code), "tradewind tradewind tradewind False True")

    @unittest.skipUnless(_installed("tradewind"), "tradewind not installed")
    def test_select_after_import_is_refused(self):
        code = (
            "import pwb_toolbox.engine as e, pwb_toolbox.backtesting\n"
            "try:\n    e.select('backtrader')\n"
            "except RuntimeError as exc:\n    print('refused')\n"
        )
        self.assertEqual(_run(code, "tradewind"), "refused")

    @unittest.skipUnless(_installed("tradewind"), "tradewind not installed")
    def test_array_feed_is_the_engines_pandas_feed_on_tradewind(self):
        code = (
            "import pwb_toolbox.backtesting as b; from pwb_toolbox.backtesting.feeds import ArrayPandasData; "
            "print(ArrayPandasData is b.bt.feeds.PandasData)"
        )
        self.assertEqual(_run(code, "tradewind"), "True")

    def test_unknown_engine_in_the_environment_is_an_error(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import pwb_toolbox.backtesting"],
            env={**os.environ, ENV: "zipline"}, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown backtest engine", proc.stderr)


if __name__ == "__main__":
    unittest.main()
