from tests.stubs import stub_environment

stub_environment()


def test_run_ib_strategy():
    stub_environment()
    from pwb_toolbox.backtest import run_ib_strategy
    bt_mod = run_ib_strategy.__globals__["bt"]

    last = {}
    original_run = bt_mod.Cerebro.run

    def recording_run(self):
        last["cerebro"] = self
        return ["ok"]

    bt_mod.Cerebro.run = recording_run

    class SimpleStrategy(bt_mod.Strategy):
        pass

    cfg = [{"dataname": "AAPL", "name": "AAPL"}]
    result = run_ib_strategy(SimpleStrategy, cfg)

    bt_mod.Cerebro.run = original_run

    cerebro = last.get("cerebro")
    assert result == ["ok"]
    assert cerebro.strategy is SimpleStrategy
    assert [d._name for d in cerebro.datas] == ["AAPL"]
