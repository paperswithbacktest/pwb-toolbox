import sys
import types
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import types


def stub_modules():
    sys.modules["pandas"] = types.ModuleType("pandas")
    pandas = sys.modules["pandas"]
    pandas.Timestamp = lambda x: x
    pandas.date_range = lambda start_date, periods=1: list(range(periods))
    pandas.MultiIndex = types.SimpleNamespace(from_product=lambda prod: list(zip(*prod)))
    class DataFrame:
        def __init__(self, value, index=None, columns=None):
            self.value = value
            self.index = index
            self.columns = columns

        def __getitem__(self, item):
            return DataFrame(self.value, index=self.index, columns=self.columns)

        def copy(self):
            return DataFrame(self.value, index=self.index, columns=self.columns)

    pandas.DataFrame = DataFrame
    global pd
    pd = pandas

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

    examples = types.ModuleType("pwb_toolbox.backtest.examples")
    alpha_mod = types.ModuleType("pwb_toolbox.backtest.examples.alpha")
    portfolio_mod = types.ModuleType("pwb_toolbox.backtest.examples.portfolio")
    execution_mod = types.ModuleType("pwb_toolbox.backtest.examples.execution")
    universe_mod = types.ModuleType("pwb_toolbox.backtest.examples.universe")
    shared_mod = types.ModuleType("pwb_toolbox.backtest.examples.shared")
    risk_mod = types.ModuleType("pwb_toolbox.backtest.examples.risk")

    class Direction:
        UP = 1
        DOWN = -1
        FLAT = 0

    class Insight:
        def __init__(self, symbol, direction, timestamp=None):
            self.symbol = symbol
            self.direction = direction
            self.timestamp = timestamp

    class AlphaModel:
        def generate(self, data):
            return []

    class GoldenCrossAlpha(AlphaModel):
        pass

    class PortfolioConstructionModel:
        def weights(self, insights, price_data=None):
            return {"SPY": 1.0}

    class EqualWeightPortfolio(PortfolioConstructionModel):
        pass

    class VolatilityWeightPortfolio(PortfolioConstructionModel):
        pass

    class Universe:
        pass

    class StaticUniverse(Universe):
        pass

    class SP500Universe(Universe):
        pass

    def rebalance(strategy, weights):
        return weights

    alpha_mod.AlphaModel = AlphaModel
    alpha_mod.GoldenCrossAlpha = GoldenCrossAlpha
    portfolio_mod.PortfolioConstructionModel = PortfolioConstructionModel
    portfolio_mod.EqualWeightPortfolio = EqualWeightPortfolio
    portfolio_mod.VolatilityWeightPortfolio = VolatilityWeightPortfolio
    execution_mod.rebalance = rebalance
    universe_mod.Universe = Universe
    universe_mod.StaticUniverse = StaticUniverse
    universe_mod.SP500Universe = SP500Universe
    shared_mod.Direction = Direction
    shared_mod.Insight = Insight
    risk_mod.max_drawdown = lambda nav: -0.1
    risk_mod.enforce_exposure_limit = lambda weights, limit: weights

    examples.AlphaModel = AlphaModel
    examples.GoldenCrossAlpha = GoldenCrossAlpha
    examples.PortfolioConstructionModel = PortfolioConstructionModel
    examples.EqualWeightPortfolio = EqualWeightPortfolio
    examples.VolatilityWeightPortfolio = VolatilityWeightPortfolio
    examples.Universe = Universe
    examples.StaticUniverse = StaticUniverse
    examples.SP500Universe = SP500Universe
    examples.rebalance = rebalance
    examples.Direction = Direction
    examples.Insight = Insight
    examples.max_drawdown = risk_mod.max_drawdown
    examples.enforce_exposure_limit = risk_mod.enforce_exposure_limit

    sys.modules["pwb_toolbox.backtest.examples"] = examples
    sys.modules["pwb_toolbox.backtest.examples.alpha"] = alpha_mod
    sys.modules["pwb_toolbox.backtest.examples.portfolio"] = portfolio_mod
    sys.modules["pwb_toolbox.backtest.examples.execution"] = execution_mod
    sys.modules["pwb_toolbox.backtest.examples.universe"] = universe_mod
    sys.modules["pwb_toolbox.backtest.examples.shared"] = shared_mod
    sys.modules["pwb_toolbox.backtest.examples.risk"] = risk_mod


def test_run_backtest():
    stub_modules()
    from pwb_toolbox.backtest import run_backtest
    from pwb_toolbox.backtest.examples import GoldenCrossAlpha, EqualWeightPortfolio

    result = run_backtest(["SPY"], GoldenCrossAlpha(), EqualWeightPortfolio(), start="2020-01-01")
    assert result == ["ok"]
