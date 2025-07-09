import math
from pwb_toolbox.backtest.risk_models import (
    TrailingStopRiskManagementModel,
    MaximumDrawdownPercentPerSecurity,
    MaximumDrawdownPercentPortfolio,
    MaximumUnrealizedProfitPercentPerSecurity,
    MaximumTotalPortfolioExposure,
    SectorExposureRiskManagementModel,
    MaximumOrderQuantityPercentPerSecurity,
    CompositeRiskManagementModel,
)


def test_trailing_stop():
    model = TrailingStopRiskManagementModel(percent=0.1)
    w = model.evaluate({"A": 1.0}, {"A": 100})
    assert w["A"] == 1.0
    w = model.evaluate({"A": 1.0}, {"A": 110})
    assert w["A"] == 1.0
    w = model.evaluate({"A": 1.0}, {"A": 98})
    assert w["A"] == 0.0


def test_max_drawdown_per_security():
    model = MaximumDrawdownPercentPerSecurity(max_drawdown=0.05)
    model.evaluate({"A": 1.0}, {"A": 100})
    w = model.evaluate({"A": 1.0}, {"A": 94})
    assert w["A"] == 0.0


def test_max_drawdown_portfolio():
    model = MaximumDrawdownPercentPortfolio(max_drawdown=0.05)
    model.evaluate({"A": 0.5, "B": 0.5}, {"A": 100, "B": 100})
    w = model.evaluate({"A": 0.5, "B": 0.5}, {"A": 90, "B": 90})
    assert all(v == 0.0 for v in w.values())


def test_max_unrealized_profit():
    model = MaximumUnrealizedProfitPercentPerSecurity(max_profit=0.1)
    model.evaluate({"A": 1.0}, {"A": 100})
    w = model.evaluate({"A": 1.0}, {"A": 111})
    assert w["A"] == 0.0


def test_max_total_portfolio_exposure():
    model = MaximumTotalPortfolioExposure(max_exposure=1.0)
    w = model.evaluate({"A": 0.7, "B": 0.7}, {"A": 100, "B": 100})
    assert math.isclose(sum(abs(v) for v in w.values()), 1.0)
    assert math.isclose(w["A"], 0.5)


def test_sector_exposure():
    model = SectorExposureRiskManagementModel(
        sector_map={"A": "Tech", "B": "Tech", "C": "Health"}, limit=0.6
    )
    w = model.evaluate({"A": 0.4, "B": 0.4, "C": 0.2}, {"A": 100, "B": 100, "C": 100})
    assert math.isclose(w["A"], 0.3)
    assert math.isclose(w["B"], 0.3)
    assert w["C"] == 0.2


def test_max_order_quantity():
    model = MaximumOrderQuantityPercentPerSecurity(max_percent=0.1)
    w1 = model.evaluate({"A": 0.2}, {"A": 100})
    assert math.isclose(w1["A"], 0.1)
    w2 = model.evaluate({"A": 0.2}, {"A": 100})
    assert math.isclose(w2["A"], 0.2)


def test_composite_risk_model():
    trailing = TrailingStopRiskManagementModel(percent=0.1)
    exposure = MaximumTotalPortfolioExposure(max_exposure=1.0)
    comp = CompositeRiskManagementModel([exposure, trailing])
    w1 = comp.evaluate({"A": 0.8, "B": 0.8}, {"A": 100, "B": 100})
    assert math.isclose(w1["A"], 0.5)
    w2 = comp.evaluate({"A": 0.5, "B": 0.5}, {"A": 88, "B": 88})
    assert all(v == 0.0 for v in w2.values())
