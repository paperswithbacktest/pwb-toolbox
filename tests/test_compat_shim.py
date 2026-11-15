"""``pwb_toolbox`` after the rename: the same modules as ``pwb``, with one warning.

The compatibility package lives in ``compat/pwb-toolbox`` (its own release,
``pwb-toolbox`` 0.2.0, which depends on ``paperswithbacktest``). Each case runs
in a subprocess with that directory on the path, because the alias installs an
import hook and files modules under two names for the life of the process.
"""

import configparser
import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPAT = os.path.join(ROOT, "compat", "pwb-toolbox")


def _run(code, *args):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (COMPAT, ROOT, env.get("PYTHONPATH", "")) if p
    )
    env.pop("PWB_BACKTEST_ENGINE", None)
    env["TQDM_DISABLE"] = "1"
    proc = subprocess.run(
        [sys.executable, *args] if code is None else [sys.executable, "-c", textwrap.dedent(code)],
        env=env, capture_output=True, text=True, check=False, cwd=ROOT,
    )
    if proc.returncode:
        raise AssertionError(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else proc.stdout)
    return proc.stdout.strip()


class CompatShimTest(unittest.TestCase):
    def test_one_deprecation_warning_naming_the_new_package(self):
        out = _run(
            """
            import warnings
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                import pwb_toolbox
                import pwb_toolbox.datasets
                import pwb_toolbox.backtesting
                import pwb_toolbox
            ours = [w for w in caught if issubclass(w.category, DeprecationWarning)
                    and "pwb_toolbox has been renamed pwb" in str(w.message)]
            print(len(ours), "paperswithbacktest" in str(ours[0].message))
            """
        )
        self.assertEqual(out, "1 True")

    def test_old_names_are_the_same_module_objects(self):
        out = _run(
            """
            import sys, warnings
            warnings.simplefilter("ignore")
            import pwb_toolbox
            import pwb_toolbox.backtesting as old_bt
            import pwb_toolbox.datasets as old_ds
            from pwb_toolbox.datasets.pit_universe import load_pit_universe
            from pwb_toolbox.backtesting import BaseStrategy, run_strategy
            import pwb, pwb.backtesting, pwb.datasets, pwb.datasets.pit_universe
            checks = [
                pwb_toolbox is pwb,
                old_bt is pwb.backtesting,
                old_ds is pwb.datasets,
                load_pit_universe is pwb.datasets.pit_universe.load_pit_universe,
                BaseStrategy is pwb.backtesting.BaseStrategy,
                run_strategy is pwb.backtesting.run_strategy,
                pwb.backtesting.__spec__.name == "pwb.backtesting",
            ]
            # nothing loaded twice: every pwb_toolbox.* entry is the pwb.* module
            for name, mod in list(sys.modules.items()):
                if name == "pwb_toolbox" or name.startswith("pwb_toolbox."):
                    checks.append(sys.modules["pwb" + name[len("pwb_toolbox"):]] is mod)
            names = {m.__name__ for n, m in sys.modules.items() if n.startswith("pwb")}
            checks.append(not any(n.startswith("pwb_toolbox") for n in names))
            print(all(checks), checks.count(False))
            """
        )
        self.assertEqual(out, "True 0")

    def test_engine_choice_is_shared(self):
        out = _run(
            """
            import warnings
            warnings.simplefilter("ignore")
            import pwb_toolbox.engine as old
            import pwb.engine as new
            old.select("tradewind")
            print(old is new, new.name())
            """
        )
        self.assertEqual(out, "True tradewind")

    def test_the_engine_runner_answers_under_the_old_name(self):
        out = _run(None, "-W", "ignore", "-m", "pwb_toolbox.engine", "--help")
        self.assertIn("--engine", out)

    def test_each_release_owns_one_import_name(self):
        main, compat = configparser.ConfigParser(), configparser.ConfigParser()
        main.read(os.path.join(ROOT, "setup.cfg"))
        compat.read(os.path.join(COMPAT, "setup.cfg"))
        self.assertEqual(main.get("metadata", "name"), "paperswithbacktest")
        self.assertEqual(main.get("options.packages.find", "include").split(), ["pwb", "pwb.*"])
        self.assertEqual(compat.get("metadata", "name"), "pwb-toolbox")
        self.assertEqual(compat.get("options", "packages").strip(), "pwb_toolbox")
        # the alias release requires at least the version it aliases
        version = main.get("metadata", "version")
        self.assertIn(f"paperswithbacktest>={version}", compat.get("options", "install_requires"))
        self.assertEqual(compat.get("metadata", "version"), version)


if __name__ == "__main__":
    unittest.main()
