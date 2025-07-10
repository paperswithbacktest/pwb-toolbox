from collections import Counter
from datetime import datetime
from typing import Mapping, Sequence, Tuple, Any, Dict


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
