from tests.stubs import pd, stub_environment
from datetime import datetime

stub_environment()

from pwb_toolbox.backtest.examples.shared import Insight, Direction
from pwb_toolbox.backtest.portfolio_models import (
    EqualWeightingPortfolioConstructionModel,
    InsightWeightingPortfolioConstructionModel,
    MeanVarianceOptimizationPortfolioConstructionModel,
    BlackLittermanOptimizationPortfolioConstructionModel,
    RiskParityPortfolioConstructionModel,
    UnconstrainedMeanVariancePortfolioConstructionModel,
    TargetPercentagePortfolioConstructionModel,
    DollarCostAveragingPortfolioConstructionModel,
    InsightRatioPortfolioConstructionModel,
)


def sample_insights(ts):
    return [
        Insight("A", Direction.UP, ts, weight=1.0),
        Insight("B", Direction.DOWN, ts, weight=2.0),
        Insight("C", Direction.UP, ts, weight=1.0),
    ]


def sample_prices(index):
    data = {
        ("A", "close"): [1, 2, 3, 4, 5],
        ("B", "close"): [2, 2.1, 2.2, 2.3, 2.4],
        ("C", "close"): [3, 2.9, 2.8, 2.7, 2.6],
    }
    return pd.DataFrame(data, index=index)


def test_equal_weighting():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    model = EqualWeightingPortfolioConstructionModel()
    w = model.weights(insights)
    assert w == {"A": 1/3, "B": -1/3, "C": 1/3}


def test_insight_weighting():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    model = InsightWeightingPortfolioConstructionModel()
    w = model.weights(insights)
    assert w == {"A": 0.25, "B": -0.5, "C": 0.25}


def test_risk_parity():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    prices = sample_prices(pd.date_range("2020-01-01", periods=5))
    model = RiskParityPortfolioConstructionModel(lookback=3)
    w = model.weights(insights, price_data=prices)
    assert round(sum(w.values()), 6) == 0.0 or round(sum(abs(v) for v in w.values()), 6) == 1.0


def test_mean_variance():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    prices = sample_prices(pd.date_range("2020-01-01", periods=60))
    model = MeanVarianceOptimizationPortfolioConstructionModel(lookback=5)
    w = model.weights(insights, price_data=prices.tail(5))
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_black_litterman():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    prices = sample_prices(pd.date_range("2020-01-01", periods=60))
    model = BlackLittermanOptimizationPortfolioConstructionModel(lookback=5)
    w = model.weights(insights, price_data=prices.tail(5))
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_unconstrained_mean_variance():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    prices = sample_prices(pd.date_range("2020-01-01", periods=5))
    model = UnconstrainedMeanVariancePortfolioConstructionModel(lookback=3)
    w = model.weights(insights, price_data=prices)
    assert set(w.keys()) == {"A", "B", "C"}


def test_target_percentage():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    model = TargetPercentagePortfolioConstructionModel({"A": 0.5, "B": 0.25, "C": 0.25})
    w = model.weights(insights)
    assert w == {"A": 0.5, "B": -0.25, "C": 0.25}


def test_dollar_cost_averaging():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    model = DollarCostAveragingPortfolioConstructionModel(allocation=0.1)
    w = model.weights(insights)
    assert w == {"A": 0.1, "B": -0.1, "C": 0.1}


def test_insight_ratio():
    ts = datetime(2020, 1, 5)
    insights = sample_insights(ts)
    model = InsightRatioPortfolioConstructionModel()
    w = model.weights(insights)
    assert w == {"A": 1/3, "B": -1/3, "C": 1/3}

