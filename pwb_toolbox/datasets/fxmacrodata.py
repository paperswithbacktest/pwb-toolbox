from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests


def load_fxmacrodata_calendar(
    currency: str = "usd",
    start_date: str | None = None,
    end_date: str | None = None,
    api_key: str | None = None,
    top_tier_only: bool = False,
    base_url: str = "https://fxmacrodata.com/api/v1",
) -> pd.DataFrame:
    """Load an FXMacroData release calendar as a pandas DataFrame."""

    params: dict[str, Any] = {}
    resolved_api_key = api_key if api_key is not None else os.getenv("FXMD_API_KEY")
    if resolved_api_key:
        params["api_key"] = resolved_api_key
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    response = requests.get(
        f"{base_url.rstrip('/')}/calendar/{currency.lower()}",
        params=params,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    rows = list((response.json() or {}).get("data") or [])
    if top_tier_only:
        rows = [row for row in rows if row.get("top_tier_for_currency") or row.get("market_tier") == 1]

    frame = pd.DataFrame(rows)
    for column in ("announcement_datetime_utc", "announcement_datetime_local"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame

