"""Tests for the per-symbol limit-order calibration added to `IBConnector`.

`_sigma_from_closes` is pure and tested directly. The `IBConnector` methods
that call into `ib_insync` are tested against a mocked `IB` client so no live
TWS/Gateway connection is required.
"""

import random
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pwb_toolbox.execution.ib_connector import IBConnector, _sigma_from_closes


def _price_path(seed, daily_vol, n=60, start=100.0):
    rng = random.Random(seed)
    prices = [start]
    for _ in range(n):
        prices.append(prices[-1] * (1 + rng.gauss(0, daily_vol)))
    return prices


# --- _sigma_from_closes (pure) ----------------------------------------------


def test_sigma_none_on_insufficient_data():
    assert _sigma_from_closes([100, 101], tick_size=0.01) is None


def test_sigma_none_on_invalid_tick_size():
    assert _sigma_from_closes([100, 101, 102, 103, 104, 105], tick_size=0) is None


def test_sigma_none_on_flat_series():
    assert _sigma_from_closes([100.0] * 10, tick_size=0.01) is None


def test_sigma_scales_with_realized_volatility():
    calm = _price_path(seed=0, daily_vol=0.002)
    wild = _price_path(seed=0, daily_vol=0.03)
    sigma_calm = _sigma_from_closes(calm, tick_size=0.01)
    sigma_wild = _sigma_from_closes(wild, tick_size=0.01)
    assert sigma_calm is not None and sigma_wild is not None
    assert sigma_wild > sigma_calm


def test_sigma_scales_inversely_with_tick_size():
    prices = _price_path(seed=1, daily_vol=0.02)
    sigma_penny = _sigma_from_closes(prices, tick_size=0.01)
    sigma_nickel = _sigma_from_closes(prices, tick_size=0.05)
    assert sigma_penny != sigma_nickel


# --- IBConnector calibration methods (mocked ib_insync.IB) -----------------


@pytest.fixture
def connector():
    ibc = IBConnector.__new__(IBConnector)  # bypass __init__/connect
    ibc.ib = MagicMock()
    return ibc


@pytest.fixture
def fake_contract():
    return SimpleNamespace(symbol="AAPL")


def test_get_tick_size_reads_min_tick(connector, fake_contract):
    connector.ib.reqContractDetails.return_value = [SimpleNamespace(minTick=0.01)]
    assert connector._get_tick_size(fake_contract) == 0.01


def test_get_tick_size_none_when_unavailable(connector, fake_contract):
    connector.ib.reqContractDetails.return_value = []
    assert connector._get_tick_size(fake_contract) is None


def test_get_sigma_uses_historical_bars(connector, fake_contract):
    prices = _price_path(seed=2, daily_vol=0.02)
    connector.ib.reqHistoricalData.return_value = [
        SimpleNamespace(close=c) for c in prices
    ]
    sigma = connector._get_sigma(fake_contract, tick_size=0.01)
    assert sigma is not None and sigma > 0


def test_get_quote_calibration_combines_both(connector, fake_contract):
    prices = _price_path(seed=3, daily_vol=0.02)
    connector.ib.reqContractDetails.return_value = [SimpleNamespace(minTick=0.01)]
    connector.ib.reqHistoricalData.return_value = [
        SimpleNamespace(close=c) for c in prices
    ]
    calibration = connector._get_quote_calibration(fake_contract)
    assert calibration.keys() == {"tick_size", "sigma"}
    assert calibration["tick_size"] == 0.01
    assert calibration["sigma"] > 0


def test_get_quote_calibration_degrades_gracefully_on_broker_errors(
    connector, fake_contract
):
    connector.ib.reqContractDetails.side_effect = Exception("no market data permission")
    connector.ib.reqHistoricalData.side_effect = Exception("no market data permission")
    # Must not raise; must fall back to no overrides so get_optimal_quote's
    # own defaults are used instead of crashing the order flow.
    assert connector._get_quote_calibration(fake_contract) == {}
