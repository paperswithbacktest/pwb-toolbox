from tests.stubs import pd, stub_environment

stub_environment()


def test_manual_universe():
    from pwb_toolbox.backtest.universe_models import ManualUniverseSelectionModel

    model = ManualUniverseSelectionModel(["A", "B"])
    assert model.symbols() == ["A", "B"]


def test_etf_constituents_universe():
    from pwb_toolbox.backtest.universe_models import ETFConstituentsUniverseSelectionModel

    model = ETFConstituentsUniverseSelectionModel("SPY")
    assert set(model.symbols()) == {"AAPL", "MSFT"}


def test_crypto_universe():
    from pwb_toolbox.backtest.universe_models import CryptoUniverseSelectionModel

    model = CryptoUniverseSelectionModel(top_n=1)
    assert model.symbols() == ["BTCUSD"]


def test_universe_chain():
    from pwb_toolbox.backtest.universe_models import (
        ManualUniverseSelectionModel,
        UniverseSelectionModelChain,
    )

    a = ManualUniverseSelectionModel(["A"])
    b = ManualUniverseSelectionModel(["B", "A"])
    chain = UniverseSelectionModelChain([a, b])
    assert chain.symbols() == ["A", "B"]


def test_scheduled_universe():
    from pwb_toolbox.backtest.universe_models import ScheduledUniverseSelectionModel

    sched = {
        "2020-01-01": ["A", "B"],
        "2020-02-01": ["C"],
    }
    model = ScheduledUniverseSelectionModel(sched)
    assert model.symbols("2020-01-15") == ["A", "B"]
    assert model.symbols("2020-02-15") == ["C"]

