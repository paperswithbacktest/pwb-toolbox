import sys
import types
import pytest

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional dep
    pytest.skip("pandas not installed", allow_module_level=True)


from tests.stubs import pd, stub_environment

stub_environment()


def test_run_backtest():
    from pwb_toolbox.backtest import run_backtest
    from pwb_toolbox.backtest.examples import GoldenCrossAlpha, EqualWeightPortfolio
    from pwb_toolbox.backtest.universe_models import ManualUniverseSelectionModel

    universe = ManualUniverseSelectionModel(["SPY"])
    result = run_backtest(
        universe,
        GoldenCrossAlpha(),
        EqualWeightPortfolio(),
        start="2020-01-01",
    )
    assert result == ["ok"]

