import sys
import types

# Minimal pandas replacement used across tests
pd = types.ModuleType("pandas")

class Series(list):
    def pct_change(self):
        return Series([None] + [self[i] / self[i - 1] - 1 for i in range(1, len(self))])

    def rolling(self, window):
        data = self

        class Rolling:
            def mean(self_inner):
                out = []
                for i in range(len(data)):
                    if i + 1 < window:
                        out.append(None)
                    else:
                        out.append(sum(data[i + 1 - window : i + 1]) / window)
                return Series(out)

            def std(self_inner):
                out = []
                for i in range(len(data)):
                    if i + 1 < window:
                        out.append(None)
                    else:
                        window_data = [x for x in data[i + 1 - window : i + 1] if x is not None]
                        if len(window_data) < window:
                            out.append(None)
                        else:
                            m = sum(window_data) / len(window_data)
                            var = sum((x - m) ** 2 for x in window_data) / len(window_data)
                            out.append(var ** 0.5)
                return Series(out)

        return Rolling()

    @property
    def iloc(self):
        series = self

        class ILoc:
            def __getitem__(self_inner, idx):
                return series[idx]

        return ILoc()


class DataFrame:
    def __init__(self, value=None, index=None, columns=None):
        self.index = list(index or range(len(next(iter(value.values())) if isinstance(value, dict) else [])))
        self.columns = list(columns or [])
        if isinstance(value, dict):
            self.data = {k: list(v) for k, v in value.items()}
        else:
            self.data = {c: [value for _ in range(len(self.index))] for c in self.columns}

    def __getitem__(self, key):
        if key in self.data:
            s = Series(self.data[key])
            s.index = self.index
            return s
        cols = [c for c in self.columns if isinstance(c, tuple) and c[0] == key]
        if cols:
            return DataFrame({c: self.data[c] for c in cols}, self.index, cols)
        raise KeyError(key)

    def copy(self):
        return DataFrame({c: list(v) for c, v in self.data.items()}, self.index, self.columns)

    @property
    def loc(self):
        df = self

        class Loc:
            def __getitem__(self_inner, item):
                return df

        return Loc()


def date_range(start, periods):
    from datetime import datetime, timedelta

    start_dt = datetime.fromisoformat(start)
    return [start_dt + timedelta(days=i) for i in range(periods)]


class IndexList(list):
    def unique(self):
        return list(dict.fromkeys(self))


class MultiIndex(IndexList):
    @classmethod
    def from_product(cls, lists):
        import itertools

        return cls(list(itertools.product(*lists)))

    def get_level_values(self, level):
        return IndexList([v[level] for v in self])


def Timestamp(val):
    from datetime import datetime

    return datetime.fromisoformat(val)


def isna(val):
    return val is None


pd.Series = Series
pd.DataFrame = DataFrame
pd.date_range = date_range
pd.MultiIndex = MultiIndex
pd.Timestamp = Timestamp
pd.isna = isna
sys.modules.setdefault("pandas", pd)


def stub_environment():
    """Install stubs for external packages used in the toolbox."""
    # backtrader
    bt = types.ModuleType("backtrader")

    class Order:
        Limit = "limit"

    class Strategy:
        def __init__(self):
            self.datas = []
            self.prices = pd.DataFrame()
            self.orders = []

        def order_target_percent(self, data=None, target=0.0):
            self.orders.append(("target", data._name, target))

        def buy(self, data=None, exectype=None, price=None):
            self.orders.append(("buy", data._name, exectype, price))

        def sell(self, data=None, exectype=None, price=None):
            self.orders.append(("sell", data._name, exectype, price))

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
    bt.Order = Order
    bt.num2date = lambda num: pd.Timestamp("2020-01-01")
    sys.modules["backtrader"] = bt

    # datasets stub
    ds = types.ModuleType("pwb_toolbox.datasets")

    def get_pricing(symbols, fields=None, start_date=None, end_date=None):
        index = pd.date_range(start_date or "2020-01-01", periods=2)
        cols = pd.MultiIndex.from_product([symbols, fields or ["close"]])
        return pd.DataFrame(1.0, index=index, columns=cols)

    ds.get_pricing = get_pricing
    sys.modules["pwb_toolbox.datasets"] = ds

    # backtest examples package stub
    examples_pkg = types.ModuleType("pwb_toolbox.backtest.examples")
    examples_pkg.__path__ = []

    shared = types.ModuleType("pwb_toolbox.backtest.examples.shared")
    class Direction:
        UP = 1
        DOWN = 2
        FLAT = 3
    class Insight:
        def __init__(self, symbol, direction, timestamp=None):
            self.symbol = symbol
            self.direction = direction
            self.timestamp = timestamp
    shared.Direction = Direction
    shared.Insight = Insight
    sys.modules["pwb_toolbox.backtest.examples.shared"] = shared

    alpha = types.ModuleType("pwb_toolbox.backtest.examples.alpha")
    class AlphaModel:
        def generate(self, data):
            return []
    class GoldenCrossAlpha(AlphaModel):
        pass
    alpha.AlphaModel = AlphaModel
    alpha.GoldenCrossAlpha = GoldenCrossAlpha
    sys.modules["pwb_toolbox.backtest.examples.alpha"] = alpha

    portfolio = types.ModuleType("pwb_toolbox.backtest.examples.portfolio")
    class PortfolioConstructionModel:
        def weights(self, insights, price_data=None):
            return {}
    class EqualWeightPortfolio(PortfolioConstructionModel):
        pass
    class VolatilityWeightPortfolio(PortfolioConstructionModel):
        pass
    portfolio.PortfolioConstructionModel = PortfolioConstructionModel
    portfolio.EqualWeightPortfolio = EqualWeightPortfolio
    portfolio.VolatilityWeightPortfolio = VolatilityWeightPortfolio
    sys.modules["pwb_toolbox.backtest.examples.portfolio"] = portfolio

    universe = types.ModuleType("pwb_toolbox.backtest.examples.universe")
    class Universe:
        def symbols(self):
            return []
    class StaticUniverse(Universe):
        def __init__(self, symbols):
            self._symbols = symbols
        def symbols(self):
            return list(self._symbols)
    class SP500Universe(Universe):
        pass
    universe.Universe = Universe
    universe.StaticUniverse = StaticUniverse
    universe.SP500Universe = SP500Universe
    sys.modules["pwb_toolbox.backtest.examples.universe"] = universe

    execution = types.ModuleType("pwb_toolbox.backtest.examples.execution")
    def rebalance(strategy, weights):
        for data in strategy.datas:
            strategy.order_target_percent(data=data, target=weights.get(data._name, 0))
    execution.rebalance = rebalance
    sys.modules["pwb_toolbox.backtest.examples.execution"] = execution

    risk = types.ModuleType("pwb_toolbox.backtest.examples.risk")
    def max_drawdown(*args, **kwargs):
        pass
    def enforce_exposure_limit(*args, **kwargs):
        pass
    risk.max_drawdown = max_drawdown
    risk.enforce_exposure_limit = enforce_exposure_limit
    sys.modules["pwb_toolbox.backtest.examples.risk"] = risk

    examples_pkg.Direction = Direction
    examples_pkg.Insight = Insight
    examples_pkg.AlphaModel = AlphaModel
    examples_pkg.GoldenCrossAlpha = GoldenCrossAlpha
    examples_pkg.PortfolioConstructionModel = PortfolioConstructionModel
    examples_pkg.EqualWeightPortfolio = EqualWeightPortfolio
    examples_pkg.VolatilityWeightPortfolio = VolatilityWeightPortfolio
    examples_pkg.Universe = Universe
    examples_pkg.StaticUniverse = StaticUniverse
    examples_pkg.SP500Universe = SP500Universe
    examples_pkg.rebalance = rebalance
    examples_pkg.max_drawdown = max_drawdown
    examples_pkg.enforce_exposure_limit = enforce_exposure_limit
    sys.modules["pwb_toolbox.backtest.examples"] = examples_pkg
