"""Which engine runs the backtests: backtrader, or Tradewind.

``pwb.backtesting`` is written against the backtrader API, and Tradewind
(``pip install tradewind``) implements that same API under the Apache 2.0 licence.
Every module of the backtesting package takes its ``bt`` from here instead of
importing backtrader itself, so the choice is made once, in one place, and the
engine that was not chosen is never imported.

How to choose, in order of precedence:

1. ``pwb.engine.select("tradewind")`` **before** ``pwb.backtesting``
   is imported. The base classes (``BaseStrategy`` is a ``bt.Strategy``) are bound
   at import time, so a choice made after that is refused rather than half applied.
2. The environment variable ``PWB_BACKTEST_ENGINE`` (``backtrader`` or ``tradewind``),
   which is how a whole campaign switches without touching a single strategy.
3. The default, ``backtrader``.

The default stays backtrader until Tradewind has reproduced the campaign's 4 200
reference NAVs; the server run is not changed by this module's existence.

Code that names ``backtrader`` itself -- the papers harness (``backtester.py``)
and the ~150 ``strategy.py`` that ``import backtrader as bt`` -- would build a
backtrader ``Cerebro`` around a Tradewind ``BaseStrategy``. :func:`use` (or the
runner below) makes the name ``backtrader`` resolve to Tradewind for this process,
so such code runs unchanged on the chosen engine; with backtrader chosen it does
nothing. It is what the grand remeasure's parity runs did by hand
(``measure_one_nav_tw*.py``), moved here so a campaign switches with one flag::

    python -m pwb.engine --engine tradewind [--report] script.py [args ...]

runs ``script.py`` as ``__main__`` on that engine; ``--report`` adds one
``ENGINE ...`` line on exit saying which engine ran and whether any module was
loaded from a backtrader package (it must be none on Tradewind).
"""

from __future__ import annotations

import importlib
import os

ENV_VAR = "PWB_BACKTEST_ENGINE"
BACKTRADER = "backtrader"
TRADEWIND = "tradewind"
ENGINES = (BACKTRADER, TRADEWIND)
DEFAULT = BACKTRADER

_selected: str | None = None  # an explicit select(), not yet loaded
_loaded: tuple[str, object] | None = None  # (name, module) once resolved


def _normalise(name) -> str:
    key = str(name).strip().lower()
    if key not in ENGINES:
        raise ValueError(
            f"unknown backtest engine {name!r}; choose one of {', '.join(ENGINES)}"
        )
    return key


def select(name: str) -> str:
    """Choose the engine for this process. Returns the normalised name.

    Must run before ``pwb.backtesting`` is imported: once the package is
    bound to an engine, asking for the other one raises ``RuntimeError`` instead
    of leaving half the classes on each engine.
    """
    global _selected
    key = _normalise(name)
    if _loaded is not None and _loaded[0] != key:
        raise RuntimeError(
            f"pwb.backtesting is already running on {_loaded[0]!r}; "
            f"select({key!r}) must be called before it is imported"
        )
    _selected = key
    return key


def name() -> str:
    """The engine in force: loaded, else selected, else the environment, else the default."""
    if _loaded is not None:
        return _loaded[0]
    if _selected is not None:
        return _selected
    return _normalise(os.getenv(ENV_VAR, DEFAULT) or DEFAULT)


def load():
    """Import and return the chosen engine module (``bt``), once per process."""
    global _loaded
    if _loaded is None:
        key = name()
        try:
            module = importlib.import_module(key)
        except ImportError as exc:  # pragma: no cover - depends on the environment
            hint = (
                "pip install tradewind" if key == TRADEWIND else "pip install backtrader"
            )
            raise ImportError(
                f"the backtest engine {key!r} is not installed ({exc}); {hint}, "
                f"or set {ENV_VAR} to one that is"
            ) from exc
        _loaded = (key, module)
    return _loaded[1]


def is_backtrader() -> bool:
    return name() == BACKTRADER


def is_tradewind() -> bool:
    return name() == TRADEWIND


# The ``backtrader`` sub-modules the corpus and the papers harness import by name.
_ALIASED_SUBMODULES = ("feeds", "indicators", "analyzers")


def alias_backtrader():
    """Make ``import backtrader`` (and its common sub-modules) give the loaded engine.

    A no-op on backtrader. On Tradewind, ``sys.modules["backtrader"]`` becomes the
    Tradewind module, with ``backtrader.feeds``/``.indicators``/``.analyzers`` and
    ``backtrader.utils.date`` (``date2num``, ``num2date``, ``num2dt``) pointing at
    Tradewind's own. Refused when the real backtrader is already imported: a
    process that holds both would mix the engines' classes. Idempotent.
    """
    import sys
    import types

    bt = load()
    if _loaded[0] != TRADEWIND:
        return bt
    current = sys.modules.get("backtrader")
    if current is bt:
        return bt
    if current is not None:
        raise RuntimeError(
            "backtrader is already imported in this process; the Tradewind alias "
            "must be installed before anything imports backtrader"
        )
    sys.modules["backtrader"] = bt
    for sub in _ALIASED_SUBMODULES:
        if hasattr(bt, sub):
            sys.modules[f"backtrader.{sub}"] = getattr(bt, sub)
    utils = types.ModuleType("backtrader.utils")
    date = types.ModuleType("backtrader.utils.date")
    for fn in ("date2num", "num2date", "num2dt"):
        if hasattr(bt, fn):
            setattr(date, fn, getattr(bt, fn))
    utils.date = date
    sys.modules["backtrader.utils"] = utils
    sys.modules["backtrader.utils.date"] = date
    return bt


def use(engine: str | None = None, alias: bool = True):
    """Select ``engine`` (default: the environment, else backtrader), load it, return ``bt``.

    With ``alias`` (the default) code that imports ``backtrader`` by name runs on
    the chosen engine too (:func:`alias_backtrader`). Like :func:`select`, it must
    run before ``pwb.backtesting`` is imported.
    """
    if engine is not None:
        select(engine)
    if alias:
        return alias_backtrader()
    return load()


def check(engine: str | None) -> str:
    """The engine in force, after checking it is ``engine`` when one is named.

    ``run_strategy(engine=...)`` calls this: the package is bound to one engine at
    import, so a run cannot switch; asking for the other one raises instead of
    silently running on the wrong engine.
    """
    current = name()
    if engine is not None and _normalise(engine) != current:
        raise RuntimeError(
            f"this process runs on {current!r}, not {_normalise(engine)!r}: the engine is "
            f"chosen before pwb.backtesting is imported -- set {ENV_VAR}="
            f"{_normalise(engine)}, call pwb.engine.use({_normalise(engine)!r}) first, "
            f"or run the script with python -m pwb.engine --engine {_normalise(engine)}"
        )
    return current


def report_line() -> str:
    """One ``ENGINE ...`` line: the engine in force and any module loaded from backtrader."""
    import os as _os
    import sys

    sep = _os.sep
    leaked = sorted(
        n for n, m in list(sys.modules.items())
        if m is not None and f"{sep}backtrader{sep}" in (getattr(m, "__file__", "") or "")
    )
    alias = sys.modules.get("backtrader")
    bt = _loaded[1] if _loaded else None
    aliased = "none" if alias is None else ("engine" if alias is bt else "backtrader")
    version = getattr(bt, "__version__", "?") if bt is not None else "?"
    return (
        f"ENGINE toolbox={name()} backtrader_name={aliased} version={version} "
        f"leaked_backtrader_modules={len(leaked)} {leaked[:5]}"
    )


def main(argv=None) -> int:
    """``python -m pwb.engine [--engine NAME] [--report] script.py [args ...]``."""
    import argparse
    import runpy
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m pwb.engine",
        description="Run a script as __main__ on the chosen backtest engine.",
    )
    parser.add_argument("--engine", choices=ENGINES, default=None,
                        help=f"default: ${ENV_VAR}, else {DEFAULT}")
    parser.add_argument("--report", action="store_true",
                        help="print one ENGINE line on exit (also on os._exit)")
    parser.add_argument("script")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)

    if ns.engine is not None:
        # Child processes the script starts inherit the choice.
        os.environ[ENV_VAR] = ns.engine
    use(ns.engine)
    if ns.report:
        import atexit

        real_exit = os._exit
        printed = []

        def _print_report():
            if not printed:
                printed.append(True)
                sys.stdout.write(report_line() + "\n")
                sys.stdout.flush()

        def _exit_with_report(code=0):
            _print_report()
            real_exit(code)

        atexit.register(_print_report)
        os._exit = _exit_with_report
    sys.argv = [ns.script] + list(ns.args)
    runpy.run_path(ns.script, run_name="__main__")
    return 0


if __name__ == "__main__":
    # ``-m`` runs this file as ``__main__``, a second copy of the module: the state
    # (the selected and loaded engine) must live in the one the package imports.
    raise SystemExit(importlib.import_module(__spec__.name).main())
