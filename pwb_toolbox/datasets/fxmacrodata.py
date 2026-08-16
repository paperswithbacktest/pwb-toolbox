from __future__ import annotations

import os
import re
from typing import Any, Mapping

import pandas as pd
import requests


FXMACRODATA_BASE_URL = "https://api.fxmacrodata.com/v1"
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


def _api_key(explicit_api_key: str | None) -> str | None:
    if explicit_api_key is not None:
        return explicit_api_key or None
    return os.getenv("FXMACRODATA_API_KEY") or os.getenv("FXMD_API_KEY")


def _currency_code(currency: str) -> str:
    value = currency.strip()
    if not _CURRENCY_RE.fullmatch(value):
        raise ValueError("currency must be a three-letter ISO currency code")
    return value.lower()


def _iso_date(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def load_fxmacrodata_calendar(
    currency: str = "usd",
    start_date: str | None = None,
    end_date: str | None = None,
    api_key: str | None = None,
    top_tier_only: bool = False,
    limit: int = 100,
    base_url: str = FXMACRODATA_BASE_URL,
    timeout: float = 30.0,
) -> pd.DataFrame:
    """Load a bounded FXMacroData release calendar as a pandas DataFrame.

    Authentication is optional for public calendar access. If ``api_key`` is
    omitted, ``FXMACRODATA_API_KEY`` and then ``FXMD_API_KEY`` are checked.
    HTTP errors deliberately omit the request URL so query-string credentials
    cannot appear in exception messages.
    """

    currency_code = _currency_code(currency)
    start = _iso_date(start_date, "start_date")
    end = _iso_date(end_date, "end_date")
    if start and end and start > end:
        raise ValueError("start_date must not be after end_date")

    limit_count = max(1, min(int(limit), 100))
    params: dict[str, Any] = {"limit": limit_count}
    resolved_api_key = _api_key(api_key)
    if resolved_api_key:
        params["api_key"] = resolved_api_key
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end

    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/calendar/{currency_code}",
            params=params,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError("FXMacroData calendar request failed") from exc
    if not response.ok:
        raise RuntimeError(
            f"FXMacroData calendar request returned HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("FXMacroData returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("FXMacroData returned an invalid response object")

    data = payload.get("data", [])
    if not isinstance(data, list):
        raise ValueError("FXMacroData response data must be a list")
    rows = [dict(row) for row in data if isinstance(row, Mapping)]
    if top_tier_only:
        rows = [
            row
            for row in rows
            if row.get("top_tier_for_currency") or row.get("market_tier") == 1
        ]

    frame = pd.DataFrame(rows[:limit_count])
    for column in ("announcement_datetime_utc", "announcement_datetime_local"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True)
    if "announcement_datetime" in frame.columns:
        frame["announcement_datetime"] = pd.to_datetime(
            frame["announcement_datetime"], errors="coerce", unit="s", utc=True
        )
    sort_column = next(
        (
            name
            for name in ("announcement_datetime", "announcement_datetime_utc", "date")
            if name in frame.columns
        ),
        None,
    )
    if sort_column:
        frame = frame.sort_values(sort_column, kind="stable").reset_index(drop=True)
    return frame
