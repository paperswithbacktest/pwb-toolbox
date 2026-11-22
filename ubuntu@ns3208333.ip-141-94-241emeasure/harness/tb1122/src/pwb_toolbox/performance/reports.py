import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import matplotlib

from .metrics import (
    total_return,
    cagr,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
)
from .plots import plot_equity_curve, plot_return_heatmap, plot_underwater
from .trade_stats import (
    average_win_loss,
    slippage_stats,
    latency_stats,
    hit_rate,
    expectancy,
    profit_factor,
    turnover,
)

# Safe for headless/server environments
matplotlib.use("Agg", force=True)


def generate_monitoring_report(
    logs_dir: Path,
    reports_dir: Path,
) -> Dict[str, Any]:
    """
    Generate a monitoring report from live-trading JSON logs.

    Parameters
    ----------
    logs_dir : Path
        Directory containing JSON log files with NAV/trade info.
        Each *.json should include:
          - 'timestamp' and 'account_nav_value' for NAV time series
          - optional 'trades': list of trade dicts
    reports_dir : Path
        Directory where plots and the text report will be saved.

    Returns
    -------
    Dict[str, Any]
        {
          'nav_metrics': {...},
          'trade_stats': {...},
          'paths': {...},
          'nav_series': pd.Series,
          'trades': List[dict]
        }
    """

    # --------------------------- helpers ---------------------------
    def _save_report(lines: List[str], out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "report.txt"
        report_path.write_text("\n".join(lines) + "\n")
        return report_path

    def _load_nav_series(src_dir: Path) -> pd.Series:
        rows: List[Dict[str, Any]] = []
        for p in src_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            ts = data.get("timestamp")
            nav = data.get("account_nav_value")
            if ts is None or nav is None:
                continue
            rows.append(
                {"timestamp": pd.to_datetime(ts, errors="coerce"), "nav": float(nav)}
            )
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows).dropna(subset=["timestamp"]).sort_values("timestamp")
        return df.set_index("timestamp")["nav"]

    def _load_trades(src_dir: Path) -> List[Dict[str, Any]]:
        trades: List[Dict[str, Any]] = []
        for p in src_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            trades.extend(data.get("trades", []))
        if not trades:
            return []
        df = pd.DataFrame(trades)
        # parse datetimes if present
        for col in ["timestamp", "entry", "exit", "signal_time", "ib_timestamp"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        records = df.to_dict(orient="records")
        # normalize numeric fields / defaults
        for t in records:
            t["return"] = float(t.get("return") or 0.0)
            t.setdefault("entry", None)
            t.setdefault("exit", None)
            t.setdefault("signal_time", None)
            t.setdefault("direction", "long")
            t["entry_price"] = float(t.get("entry_price") or 0.0)
            t["model_entry_price"] = float(t.get("model_entry_price") or 0.0)
            t["exit_price"] = float(t.get("exit_price") or 0.0)
            t["model_exit_price"] = float(t.get("model_exit_price") or 0.0)
        return records

    # --------------------------- load ------------------------------
    lines: List[str] = []
    if not logs_dir.exists():
        lines.append(f"Logs directory not found: {logs_dir}")
        report_path = _save_report(lines, reports_dir)
        return {
            "nav_metrics": {},
            "trade_stats": {},
            "paths": {"report_txt": str(report_path)},
            "nav_series": pd.Series(dtype=float),
            "trades": [],
        }

    nav_series = _load_nav_series(logs_dir)
    trades = _load_trades(logs_dir)

    # --------------------------- plots -----------------------------
    eq_path = reports_dir / "equity_curve.png"
    rh_path = reports_dir / "return_heatmap.png"
    uw_path = reports_dir / "underwater.png"

    reports_dir.mkdir(parents=True, exist_ok=True)
    plot_equity_curve(nav_series).figure.savefig(eq_path)
    plot_return_heatmap(nav_series).figure.savefig(rh_path)
    plot_underwater(nav_series).figure.savefig(uw_path)

    # --------------------------- metrics ---------------------------
    nav_metrics = {
        "total_return": float(total_return(nav_series) or 0.0),
        "cagr": float(cagr(nav_series) or 0.0),
        "ann_vol": float(annualized_volatility(nav_series) or 0.0),
        "max_dd": float(max_drawdown(nav_series)[0] if len(nav_series) else 0.0),
        "sharpe": float(sharpe_ratio(nav_series) or 0.0),
    }

    avg_win, avg_loss = average_win_loss(trades) if trades else (0.0, 0.0)
    slip = (
        slippage_stats(trades)
        if trades
        else {"avg_entry_slippage": 0.0, "avg_exit_slippage": 0.0}
    )
    latency = (
        latency_stats(trades)
        if trades
        else {"avg_latency_sec": 0.0, "max_latency_sec": 0.0}
    )

    trade_stats = {
        "hit_rate": float(hit_rate(trades) or 0.0),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "expectancy": float(expectancy(trades) or 0.0),
        "profit_factor": float(profit_factor(trades) or 0.0),
        "turnover_per_day": float(turnover(trades) or 0.0),
        "entry_slippage": float(slip.get("avg_entry_slippage", 0.0)),
        "exit_slippage": float(slip.get("avg_exit_slippage", 0.0)),
        "avg_latency_sec": float(latency.get("avg_latency_sec", 0.0)),
        "max_latency_sec": float(latency.get("max_latency_sec", 0.0)),
    }

    # --------------------------- report text -----------------------
    def _fperc(x: float) -> str:
        return f"{x:.2%}"

    def _f(x: float, n: int = 4) -> str:
        return f"{x:.{n}f}"

    lines.extend(
        [
            "NAV Metrics:",
            f"Total Return:          {_fperc(nav_metrics['total_return'])}",
            f"CAGR:                  {_fperc(nav_metrics['cagr'])}",
            f"Annualized Volatility: {_fperc(nav_metrics['ann_vol'])}",
            f"Max Drawdown:          {_fperc(nav_metrics['max_dd'])}",
            f"Sharpe Ratio:          {nav_metrics['sharpe']:.2f}",
            "",
            "Trade Statistics:",
            f"Hit Rate:              {_fperc(trade_stats['hit_rate'])}",
            f"Avg Win/Loss:          {_f(trade_stats['avg_win'])}/{_f(trade_stats['avg_loss'])}",
            f"Expectancy:            {_f(trade_stats['expectancy'])}",
            f"Profit Factor:         {_f(trade_stats['profit_factor'], 2)}",
            f"Turnover:              {_f(trade_stats['turnover_per_day'], 2)}/day",
            f"Entry Slippage:        {_f(trade_stats['entry_slippage'])}",
            f"Exit Slippage:         {_f(trade_stats['exit_slippage'])}",
            f"Avg Latency (s):       {_f(trade_stats['avg_latency_sec'], 2)}",
            f"Max Latency (s):       {_f(trade_stats['max_latency_sec'], 2)}",
        ]
    )

    report_path = _save_report(lines, reports_dir)

    return {
        "nav_metrics": nav_metrics,
        "trade_stats": trade_stats,
        "paths": {
            "report_txt": str(report_path),
            "equity_curve_png": str(eq_path),
            "return_heatmap_png": str(rh_path),
            "underwater_png": str(uw_path),
        },
        "nav_series": nav_series,
        "trades": trades,
    }
