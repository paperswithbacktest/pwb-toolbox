"""Which engine runs the backtests: backtrader, or Tradewind.

``pwb_toolbox.backtesting`` is written against the backtrader API, and Tradewind
(``pip install tradewind``) implements that same API under the Apache 2.0 licence.
Every module of the backtesting package takes its ``bt`` from here instead of
importing backtrader itself, so the choice is made once, in one place, and the
engine that was not chosen is never imported.

How to choose, in order of precedence:

1. ``pwb_toolbox.engine.select("tradewind")`` **before** ``pwb_toolbox.backtesting``
   is imported. The base classes (``BaseStrategy`` is a ``bt.Strategy``) are bound
   at import time, so a choice made after that is refused rather than half applied.
2. The environment variable ``PWB_BACKTEST_ENGINE`` (``backtrader`` or ``tradewind``),
   which is how a whole campaign switches without touching a single strategy.
3. The default, ``backtrader``.

The default stays backtrader until Tradewind has reproduced the campaign's 4 200
reference NAVs; the server run is not changed by this module's existence.
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

    Must run before ``pwb_toolbox.backtesting`` is imported: once the package is
    bound to an engine, asking for the other one raises ``RuntimeError`` instead
    of leaving half the classes on each engine.
    """
    global _selected
    key = _normalise(name)
    if _loaded is not None and _loaded[0] != key:
        raise RuntimeError(
            f"pwb_toolbox.backtesting is already running on {_loaded[0]!r}; "
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
