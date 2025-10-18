import logging
import os
from pathlib import Path
import requests

import pandas as pd

import pwb_toolbox.execution as pwb_exec


logs_dir = Path.home() / "pwb-fund-data" / "strategies" / "all" / "execution_logs"
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)


LEVERAGE = 2
ACCOUNT_REFERENCE_NAV_VALUE = 1_000_000.0  # Reference NAV value for scaling
ACCOUNT_REFERENCE_NAV_DATE = pd.to_datetime("2024-01-01")


def get_meta_strategy():
    """Get meta strategy data"""
    response = requests.get(
        "https://paperswithbacktest.com/api/v1/meta-strategy",
        headers={"x-api-key": os.getenv("PWB_API_KEY")},
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("settings", {})


def execute():
    """Main entrypoint"""
    meta_strategy = get_meta_strategy()

    ibc = pwb_exec.IBConnector(
        market_data_type=3,  # 1 = real-time, 2 = frozen, 3 = delayed, 4 = delayed-frozen
    )
    ibc.connect()

    account_nav_value = ibc.get_account_nav()
    account_nav_date = pd.Timestamp.today().normalize()

    nav_entry = pwb_exec.append_nav_history(logs_dir, account_nav_value)

    daily_nav_df = pd.DataFrame(meta_strategy["performance"])
    daily_nav_df["date"] = pd.to_datetime(daily_nav_df["date"])
    daily_nav_df.set_index("date", inplace=True)

    pos = daily_nav_df.index.get_indexer(
        [ACCOUNT_REFERENCE_NAV_DATE], method="nearest"
    )[0]
    backtest_nav_value = daily_nav_df.iloc[pos]
    adjustment_factor = ACCOUNT_REFERENCE_NAV_VALUE / backtest_nav_value * LEVERAGE
    target_positions = {
        elem["ticker"]: elem["position"] * adjustment_factor
        for elem in meta_strategy["positions"]
    }

    ib_positions = ibc.get_positions()

    orders = pwb_exec.compute_orders(
        target_positions=target_positions,
        current_positions=ib_positions,
    )

    trades = pwb_exec.execute_and_log_orders(
        connector=ibc,
        orders=orders,
        execution_time=5 * 60,  # 5 minutes
    )

    pwb_exec.log_current_state(
        logs_dir=logs_dir,
        account_nav_value=account_nav_value,
        strategies_positions=meta_strategy["positions"],
        target_positions=target_positions,
        current_positions=ib_positions,
        orders=orders,
        account_nav_date=account_nav_date,
        trades=trades,
        nav_history_entry=nav_entry,
    )

    ibc.disconnect()


if __name__ == "__main__":
    execute()
