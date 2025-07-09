import sys
import types

# Minimal pandas replacement used across tests
pd = types.ModuleType("pandas")

class Series(list):
    def __init__(self, data=None):
        if isinstance(data, dict):
            super().__init__(list(data.values()))
            self.index = list(data.keys())
        else:
            super().__init__(data or [])
            self.index = list(range(len(self)))

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

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        if isinstance(key, slice):
            return Series(list(self)[key])
        if key in self.index:
            return super().__getitem__(self.index.index(key))
        raise KeyError(key)

    def __eq__(self, other):
        return Series([x == other for x in self])

    def unique(self):
        return list(dict.fromkeys(self))

    @property
    def values(self):
        return list(self)

    @property
    def loc(self):
        series = self

        class Loc:
            def __getitem__(self_inner, item):
                if isinstance(item, list):
                    return Series([series[series.index.index(i)] for i in item])
                return series[series.index.index(item)]

        return Loc()

    def __add__(self, other):
        if isinstance(other, Series):
            s = Series([
                (a + b if a is not None and b is not None else None)
                for a, b in zip(self, other)
            ])
            s.index = self.index
            return s
        if isinstance(other, (int, float)):
            s = Series([(a + other if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Series):
            s = Series([
                (a - b if a is not None and b is not None else None)
                for a, b in zip(self, other)
            ])
            s.index = self.index
            return s
        if isinstance(other, (int, float)):
            s = Series([(a - other if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            s = Series([(other - a if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, Series):
            s = Series([
                (a * b if a is not None and b is not None else None)
                for a, b in zip(self, other)
            ])
            s.index = self.index
            return s
        if isinstance(other, (int, float)):
            s = Series([(a * other if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, Series):
            s = Series([
                (a / b if a is not None and b is not None else None)
                for a, b in zip(self, other)
            ])
            s.index = self.index
            return s
        if isinstance(other, (int, float)):
            s = Series([(a / other if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            s = Series([(other / a if a is not None else None) for a in self])
            s.index = self.index
            return s
        return NotImplemented

    @property
    def iloc(self):
        series = self

        class ILoc:
            def __getitem__(self_inner, idx):
                return series[idx]

        return ILoc()


class DataFrame:
    def __init__(self, value=None, index=None, columns=None):
        if isinstance(value, dict):
            max_len = len(index) if index is not None else max(len(v) for v in value.values())
            self.index = list(index or range(max_len))
            if columns is None:
                col_list = list(value.keys())
                if col_list and all(isinstance(c, tuple) for c in col_list):
                    self.columns = MultiIndex(col_list)
                else:
                    self.columns = col_list
            else:
                self.columns = columns if isinstance(columns, MultiIndex) else list(columns)
            self.data = {
                k: ([v[0]] * (max_len - len(v)) if len(v) < max_len else []) + list(v)
                for k, v in value.items()
            }
        else:
            self.index = list(index or [])
            self.columns = columns if isinstance(columns, MultiIndex) else list(columns or [])
            self.data = {c: [value for _ in range(len(self.index))] for c in self.columns}

    def __len__(self):
        return len(self.index)

    def __getitem__(self, key):
        if isinstance(key, list) and len(key) == len(self.index) and all(isinstance(x, bool) for x in key):
            new_index = [idx for idx, m in zip(self.index, key) if m]
            return DataFrame(
                {c: [v for v, m in zip(self.data[c], key) if m] for c in self.columns},
                new_index,
                self.columns,
            )
        if isinstance(key, list):
            cols = []
            for k in key:
                if k in self.data:
                    cols.append(k)
                else:
                    cols.extend(
                        [c for c in self.columns if isinstance(c, tuple) and c[0] == k]
                    )
            cols_list = cols
            new_cols = (
                MultiIndex(cols_list)
                if isinstance(self.columns, MultiIndex)
                else cols_list
            )
            return DataFrame({c: self.data[c] for c in cols_list}, self.index, new_cols)
        if key in self.data:
            s = Series(self.data[key])
            s.index = self.index
            return s
        cols = [c for c in self.columns if isinstance(c, tuple) and c[0] == key]
        if cols:
            new_cols = MultiIndex(cols) if isinstance(self.columns, MultiIndex) else cols
            return DataFrame({c: self.data[c] for c in cols}, self.index, new_cols)
        if (
            len(self.columns) == 1
            and isinstance(self.columns[0], tuple)
            and self.columns[0][1] == key
        ):
            s = Series(self.data[self.columns[0]])
            s.index = self.index
            return s
        raise KeyError(key)

    def tail(self, n):
        start = max(len(self.index) - n, 0)
        return DataFrame(
            {c: v[start:] for c, v in self.data.items()},
            self.index[start:],
            self.columns,
        )

    def pct_change(self):
        return DataFrame(
            {c: Series(v).pct_change() for c, v in self.data.items()},
            self.index,
            self.columns,
        )

    def xs(self, key, axis=1, level=-1):
        if axis != 1:
            raise NotImplementedError
        cols = [c for c in self.columns if isinstance(c, tuple) and c[level] == key]
        new_cols = [c[0] if level == -1 else c[1] for c in cols]
        new_data = {new_cols[i]: self.data[cols[i]] for i in range(len(cols))}
        return DataFrame(new_data, self.index, new_cols)

    def dropna(self):
        valid = [
            i
            for i in range(len(self.index))
            if all(self.data[c][i] is not None for c in self.columns)
        ]
        return DataFrame(
            {c: [self.data[c][i] for i in valid] for c in self.columns},
            [self.index[i] for i in valid],
            self.columns,
        )

    def mean(self):
        vals = []
        for c in self.columns:
            data = [x for x in self.data[c] if x is not None]
            vals.append(sum(data) / len(data))
        s = Series(vals)
        s.index = self.columns
        return s

    def cov(self):
        cols = self.columns
        matrix = []
        n = len(self.index)
        for c1 in cols:
            row = []
            x = self.data[c1]
            mean_x = sum(x) / len(x)
            for c2 in cols:
                y = self.data[c2]
                mean_y = sum(y) / len(y)
                cov_xy = sum((x[k] - mean_x) * (y[k] - mean_y) for k in range(n)) / n
                row.append(cov_xy)
            matrix.append(row)
        df = DataFrame({c: [row[i] for row in matrix] for i, c in enumerate(cols)}, cols, cols)
        df._matrix = matrix
        return df

    @property
    def values(self):
        if hasattr(self, "_matrix"):
            return self._matrix
        return [self.data[c] for c in self.columns]

    @property
    def empty(self):
        return all(len(v) == 0 for v in self.data.values())

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

# minimal numpy replacement
np = types.ModuleType("numpy")
np.ndarray = list
np.array = lambda x: list(x)
np.sum = lambda x: sum(x)
def _abs(x):
    if isinstance(x, list):
        return [abs(v) for v in x]
    return abs(x)

np.abs = _abs
def _pinv(x):
    size = len(x)
    class Mat(list):
        def dot(self_inner, vec):
            res = [sum(self_inner[i][j] * vec[j] for j in range(len(vec))) for i in range(size)]
            res = [abs(r) for r in res]
            total = sum(res) or 1
            return Series([r / total for r in res])
    return Mat([[1 if i == j else 0 for j in range(size)] for i in range(size)])

np.linalg = types.SimpleNamespace(pinv=_pinv)
sys.modules.setdefault("numpy", np)


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

    def load_dataset(name, symbols=None, **kwargs):
        if name == "ETF-Constituents":
            return pd.DataFrame(
                {
                    "etf": ["SPY", "SPY", "QQQ"],
                    "symbol": ["AAPL", "MSFT", "AAPL"],
                }
            )
        if name == "Cryptocurrencies-Daily-Price":
            return pd.DataFrame({"symbol": ["BTCUSD", "ETHUSD"]})
        return pd.DataFrame({"symbol": symbols or []})

    ds.get_pricing = get_pricing
    ds.load_dataset = load_dataset
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
        def __init__(self, symbol, direction, timestamp=None, weight=1.0):
            self.symbol = symbol
            self.direction = direction
            self.timestamp = timestamp
            self.weight = weight
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
