import sys
import types
import pandas as pd


def stub_modules():
    bt = types.ModuleType("backtrader")

    class Strategy:
        params = ()

        def __init__(self, *args, **kwargs):
            pass

        def order_target_percent(self, data=None, target=0.0):
            pass

    class Cerebro:
        def __init__(self):
            self.datas = []
            self.broker = types.SimpleNamespace(setcash=lambda cash: None)

        def addstrategy(self, strategy, **kwargs):
            self.strategy = strategy
            self.kwargs = kwargs

        def adddata(self, data, name=None):
            self.datas.append(types.SimpleNamespace(_name=name))

        def run(self):
            return ["ok"]

    class Feeds:
        class PandasData:
            def __init__(self, dataname):
                self.dataname = dataname

    bt.Strategy = Strategy
    bt.Cerebro = Cerebro
    bt.feeds = Feeds
    bt.num2date = lambda num: pd.Timestamp("2020-01-01")
    sys.modules["backtrader"] = bt

    ds = types.ModuleType("pwb_toolbox.datasets")

    def get_pricing(symbols, fields=None, start_date=None, end_date=None):
        index = pd.date_range(start_date, periods=2)
        cols = pd.MultiIndex.from_product([symbols, fields or ["close"]])
        return pd.DataFrame(1.0, index=index, columns=cols)

    ds.get_pricing = get_pricing
    sys.modules["pwb_toolbox.datasets"] = ds


def test_run_backtest():
    stub_modules()
    from pwb_toolbox.backtest import run_backtest
    from pwb_toolbox.backtest.examples import GoldenCrossAlpha, EqualWeightPortfolio

    result = run_backtest(["SPY"], GoldenCrossAlpha(), EqualWeightPortfolio(), start="2020-01-01")
    assert result == ["ok"]
