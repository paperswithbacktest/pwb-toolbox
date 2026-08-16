from unittest.mock import Mock, patch

import pandas as pd
import pytest

from pwb_toolbox.datasets.fxmacrodata import load_fxmacrodata_calendar


def _response(payload, *, status_code=200):
    response = Mock()
    response.ok = status_code < 400
    response.status_code = status_code
    response.json.return_value = payload
    return response


@patch("pwb_toolbox.datasets.fxmacrodata.requests.get")
def test_load_calendar_builds_bounded_request_and_normalizes_timestamps(get):
    get.return_value = _response(
        {
            "data": [
                {
                    "indicator": "inflation",
                    "market_tier": 1,
                    "announcement_datetime": 1786492800,
                }
            ]
        }
    )

    frame = load_fxmacrodata_calendar(
        "USD",
        "2026-08-01",
        "2026-08-31",
        limit=500,
    )

    assert list(frame["indicator"]) == ["inflation"]
    assert isinstance(frame.loc[0, "announcement_datetime"], pd.Timestamp)
    url = get.call_args.args[0]
    params = get.call_args.kwargs["params"]
    assert url == "https://api.fxmacrodata.com/v1/calendar/usd"
    assert params == {
        "limit": 100,
        "start_date": "2026-08-01",
        "end_date": "2026-08-31",
    }


@patch("pwb_toolbox.datasets.fxmacrodata.requests.get")
def test_load_calendar_uses_environment_key_without_leaking_it(get, monkeypatch):
    get.return_value = _response({}, status_code=401)
    monkeypatch.setenv("FXMACRODATA_API_KEY", "test-secret")

    with pytest.raises(RuntimeError) as exc_info:
        load_fxmacrodata_calendar()

    assert "test-secret" not in str(exc_info.value)
    assert get.call_args.kwargs["params"]["api_key"] == "test-secret"


@patch("pwb_toolbox.datasets.fxmacrodata.requests.get")
def test_load_calendar_filters_top_tier_and_ignores_non_object_rows(get):
    get.return_value = _response(
        {
            "data": [
                {"indicator": "inflation", "market_tier": 1},
                {"indicator": "trade_balance", "market_tier": 3},
                "invalid",
            ]
        }
    )

    frame = load_fxmacrodata_calendar(top_tier_only=True)

    assert list(frame["indicator"]) == ["inflation"]


@pytest.mark.parametrize("currency", ["", "US", "US_D", "123"])
def test_load_calendar_rejects_invalid_currency(currency):
    with pytest.raises(ValueError, match="three-letter"):
        load_fxmacrodata_calendar(currency)


def test_load_calendar_rejects_reversed_dates():
    with pytest.raises(ValueError, match="start_date"):
        load_fxmacrodata_calendar(start_date="2026-08-02", end_date="2026-08-01")
