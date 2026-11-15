from collections import Counter
from datetime import datetime
from typing import Mapping, Sequence, Tuple, Any, Dict, List


def hit_rate(trades: Sequence[Mapping[str, Any]]) -> float:
    """Proportion of trades with positive return."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.get("return", 0) > 0)
    return wins / len(trades)


def average_win_loss(trades: Sequence[Mapping[str, Any]]) -> Tuple[float, float]:
    """Average winning and losing trade returns."""
    wins = [t.get("return", 0) for t in trades if t.get("return", 0) > 0]
    losses = [t.get("return", 0) for t in trades if t.get("return", 0) < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return avg_win, avg_loss


def expectancy(trades: Sequence[Mapping[str, Any]]) -> float:
    """Expected return per trade."""
    hr = hit_rate(trades)
    avg_win, avg_loss = average_win_loss(trades)
    return hr * avg_win + (1 - hr) * avg_loss


def profit_factor(trades: Sequence[Mapping[str, Any]]) -> float:
    """Ratio of gross profits to gross losses."""
    gains = sum(t.get("return", 0) for t in trades if t.get("return", 0) > 0)
    losses = -sum(t.get("return", 0) for t in trades if t.get("return", 0) < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def trade_duration_distribution(trades: Sequence[Mapping[str, Any]]) -> Dict[int, int]:
    """Distribution of trade holding periods in days."""
    durations = []
    for t in trades:
        entry = t.get("entry")
        exit_ = t.get("exit")
        if entry is None or exit_ is None:
            continue
        delta = exit_ - entry
        days = delta.days if hasattr(delta, "days") else int(delta)
        durations.append(days)
    return dict(Counter(durations))


def turnover(trades: Sequence[Mapping[str, Any]]) -> float:
    """Average number of trades per day."""
    if not trades:
        return 0.0
    entries = [t.get("entry") for t in trades if t.get("entry") is not None]
    exits = [t.get("exit") for t in trades if t.get("exit") is not None]
    if not entries or not exits:
        return 0.0
    start = min(entries)
    end = max(exits)
    period = (end - start).days
    if period <= 0:
        return float(len(trades))
    return len(trades) / period


def trade_implementation_shortfall(trade: Mapping[str, Any]) -> float:
    """Implementation shortfall for a single trade.

    Calculated as the difference between the modelled return and the
    realised return of the trade.  If either value is missing the result
    is ``0.0``.
    """

    model_ret = trade.get("model_return")
    actual_ret = trade.get("return")
    if model_ret is None or actual_ret is None:
        return 0.0
    return model_ret - actual_ret


def cumulative_implementation_shortfall(trades: Sequence[Mapping[str, Any]]) -> float:
    """Total implementation shortfall over a collection of trades."""

    return sum(trade_implementation_shortfall(t) for t in trades)


def slippage_stats(trades: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    """Average entry and exit slippage for a set of trades.

    Slippage is measured relative to the model prices.  Positive values
    indicate worse execution than the modelled price.
    """

    entry_slip: List[float] = []
    exit_slip: List[float] = []

    for t in trades:
        # Default to a long direction when the field is missing.  Real trading logs
        # are expected to include a ``direction`` column with values like
        # ``"long"`` or ``"short"`` (case insensitive).
        direction = 1 if str(t.get("direction", "long")).lower() == "long" else -1

        if "entry_price" in t and "model_entry_price" in t and t["model_entry_price"]:
            entry_slip.append(
                direction
                * (t["entry_price"] - t["model_entry_price"]) / t["model_entry_price"]
            )

        if "exit_price" in t and "model_exit_price" in t and t["model_exit_price"]:
            exit_slip.append(
                direction
                * (t["model_exit_price"] - t["exit_price"]) / t["model_exit_price"]
            )

    avg_entry = sum(entry_slip) / len(entry_slip) if entry_slip else 0.0
    avg_exit = sum(exit_slip) / len(exit_slip) if exit_slip else 0.0
    return {"avg_entry_slippage": avg_entry, "avg_exit_slippage": avg_exit}


def latency_stats(trades: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    """Basic latency metrics in seconds between signal and execution."""

    latencies = []
    for t in trades:
        signal_time = t.get("signal_time")
        entry_time = t.get("entry")
        if signal_time is None or entry_time is None:
            continue
        delta = entry_time - signal_time
        secs = delta.total_seconds() if hasattr(delta, "total_seconds") else float(delta)
        latencies.append(secs)

    if not latencies:
        return {"avg_latency_sec": 0.0, "max_latency_sec": 0.0}

    avg_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    return {"avg_latency_sec": avg_lat, "max_latency_sec": max_lat}
