import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.test_backtest import stub_modules

stub_modules()

from pwb_toolbox.backtest.risk_models import (
    Position,
    TrailingStopRiskManagementModel,
    MaximumDrawdownPercentPerSecurity,
    MaximumDrawdownPercentPortfolio,
    MaximumUnrealizedProfitPercentPerSecurity,
    MaximumTotalPortfolioExposure,
    SectorExposureRiskManagementModel,
    MaximumOrderQuantityPercentPerSecurity,
    CompositeRiskManagementModel,
)


def make_pos(price, entry, quantity=1.0, sector="tech"):
    return Position("A", quantity, price, entry, sector)


def test_trailing_stop():
    model = TrailingStopRiskManagementModel(0.1)
    p = make_pos(110, 100)
    assert model.evaluate([p])["A"] == 1.0
    p = make_pos(98, 100)
    assert model.evaluate([p])["A"] == 0.0


def test_max_drawdown_per_security():
    model = MaximumDrawdownPercentPerSecurity(0.2)
    p = make_pos(100, 100)
    assert model.evaluate([p])["A"] == 1.0
    p = make_pos(75, 100)
    assert model.evaluate([p])["A"] == 0.0


def test_max_drawdown_portfolio():
    model = MaximumDrawdownPercentPortfolio(0.1)
    p = make_pos(100, 100)
    assert model.evaluate([p])["A"] == 1.0
    p = make_pos(89, 100)
    assert model.evaluate([p])["A"] == 0.0


def test_max_unrealized_profit_per_security():
    model = MaximumUnrealizedProfitPercentPerSecurity(0.05)
    p = make_pos(104, 100)
    assert model.evaluate([p])["A"] == 1.0
    p = make_pos(106, 100)
    assert model.evaluate([p])["A"] == 0.0


def test_max_total_portfolio_exposure():
    model = MaximumTotalPortfolioExposure(0.5)
    p1 = Position("A", 0.6, 100, 100)
    p2 = Position("B", 0.4, 100, 100)
    res = model.evaluate([p1, p2])
    assert abs(res["A"] - 0.3) < 1e-6
    assert abs(res["B"] - 0.2) < 1e-6


def test_sector_exposure_limit():
    model = SectorExposureRiskManagementModel(0.5)
    p1 = Position("A", 0.6, 100, 100, sector="tech")
    p2 = Position("B", 0.4, 100, 100, sector="finance")
    res = model.evaluate([p1, p2])
    assert abs(res["A"] - 0.5) < 1e-6
    assert abs(res["B"] - 0.4) < 1e-6


def test_max_order_quantity_percent_per_security():
    model = MaximumOrderQuantityPercentPerSecurity(0.4)
    p = Position("A", 0.6, 100, 100)
    assert model.evaluate([p])["A"] == 0.4


def test_composite_model():
    m1 = MaximumOrderQuantityPercentPerSecurity(0.5)
    m2 = MaximumTotalPortfolioExposure(0.8)
    comp = CompositeRiskManagementModel([m1, m2])
    p1 = Position("A", 0.6, 100, 100)
    p2 = Position("B", 0.6, 100, 100)
    res = comp.evaluate([p1, p2])
    assert abs(res["A"] - 0.4) < 1e-6
    assert abs(res["B"] - 0.4) < 1e-6
