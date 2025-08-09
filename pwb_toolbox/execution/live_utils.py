import importlib
import json
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Any

import pandas as pd


def append_nav_history(logs_dir: Path, account_nav_value: float) -> Dict[str, Any]:
    """Return a NAV history entry for the current timestamp."""
    return {
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "account_nav_value": account_nav_value,
    }


def run_strategies(
    strategies: Dict[str, Dict[str, float]],
) -> Tuple[Dict[str, pd.Series], Dict[str, Dict[str, float]]]:
    """Run strategy modules and collect NAV series and raw positions."""
    nav_series: Dict[str, pd.Series] = {}
    raw_positions: Dict[str, Dict[str, float]] = {}
    for name, spec in strategies.items():
        print(f"Running strategy: {name}")
        bt_mod = importlib.import_module(spec["path"])
        bt_result = bt_mod.run_strategy()
        raw_positions[name] = bt_result.get_latest_positions()
        nav = pd.Series(
            [row["value"] for row in bt_result.log_data],
            index=pd.to_datetime([row["date"] for row in bt_result.log_data]),
            name=name,
            dtype=float,
        ).sort_index()
        nav_series[name] = nav
    return nav_series, raw_positions


def scale_positions(
    strategies: Dict[str, Dict[str, float]],
    raw_positions: Dict[str, Dict[str, float]],
    nav_series: Dict[str, pd.Series],
    account_reference_nav_value: float,
    leverage: float,
    account_reference_nav_date: pd.Timestamp,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    """Scale raw positions to current account value and leverage."""
    weights = pd.Series(
        {name: spec["weight"] for name, spec in strategies.items()}, dtype=float
    )
    weights /= weights.sum()

    theoretical_positions: Dict[str, float] = {}
    strategies_positions: Dict[str, Dict[str, float]] = {}
    for name, spec in strategies.items():
        daily_nav_df = nav_series[name]
        pos = daily_nav_df.index.get_indexer(
            [account_reference_nav_date], method="nearest"
        )[0]
        backtest_nav_value = daily_nav_df.iloc[pos]
        adjustment_factor = (
            (account_reference_nav_value * weights[name])
            / backtest_nav_value
            * leverage
        )
        scaled_positions: Dict[str, float] = {}
        for symbol, position in raw_positions[name].items():
            scaled = position * adjustment_factor
            theoretical_positions[symbol] = (
                theoretical_positions.get(symbol, 0) + scaled
            )
            scaled_positions[symbol] = scaled
        strategies_positions[name] = scaled_positions
    return strategies_positions, theoretical_positions


def compute_orders(
    theoretical_positions: Dict[str, float], current_positions: Dict[str, float]
) -> Dict[str, float]:
    """Calculate order quantities required to move from current to target positions."""
    orders: Dict[str, float] = {}
    for symbol, target_qty in theoretical_positions.items():
        current_qty = current_positions.get(symbol, 0.0)
        diff = target_qty - current_qty
        if abs(diff) > 0:
            orders[symbol] = diff
    for symbol, current_qty in current_positions.items():
        if symbol not in theoretical_positions and current_qty != 0:
            orders[symbol] = -current_qty
    return orders


def log_current_state(
    logs_dir: Path,
    account_nav_value: float,
    strategies_positions: Dict[str, Dict[str, float]],
    theoretical_positions: Dict[str, float],
    current_positions: Dict[str, float],
    orders: Dict[str, float],
    account_nav_date: pd.Timestamp,
    trades: Optional[List[Dict[str, Any]]] = None,
    nav_history_entry: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist current run state to a JSON file."""
    log_data = {
        "timestamp": pd.Timestamp.utcnow().isoformat(),
        "account_nav_value": account_nav_value,
        "strategies_positions": strategies_positions,
        "theoretical_positions": theoretical_positions,
        "positions": current_positions,
        "orders": orders,
    }
    if nav_history_entry is not None:
        log_data["nav_history"] = [nav_history_entry]
    if trades is not None:
        log_data["trades"] = trades
    log_file = logs_dir / f"{account_nav_date.strftime('%Y-%m-%d')}.json"
    with log_file.open("w") as f:
        json.dump(log_data, f, indent=2, sort_keys=True)


def execute_and_log_orders(
    connector,
    orders: Dict[str, float],
    execution_time: int,
) -> List[Dict[str, Any]]:
    """Execute orders via connector and return executed trades."""
    trades = connector.execute_orders(orders, time_in_seconds=execution_time)
    trade_dicts: List[Dict[str, Any]] = []
    for record in trades:
        trade_dict = record.as_dict()
        trade_dicts.append(trade_dict)
        print(
            f"Executed {record.order_type} order for {record.symbol} {record.action} {record.quantity}"
        )
    return trade_dicts
