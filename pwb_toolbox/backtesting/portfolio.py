import importlib
import json
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import pwb_toolbox.performance as pwb_perf


def run_portfolio(strategies: Dict[str, Dict[str, Any]], leverage: float = 1.0, initial_cash: float = 100_000.0) -> pd.Series:
    """Run multiple strategies and aggregate their NAVs into a single portfolio.

    Parameters
    ----------
    strategies : mapping
        Dict mapping strategy name to a dict with keys:
            * ``path``: import path to strategy module containing ``run_strategy``.
            * ``weight``: target portfolio weight.
    leverage : float, optional
        Portfolio leverage factor.
    initial_cash : float, optional
        Starting capital for the portfolio.

    Returns
    -------
    pandas.Series
        Daily net asset value of the aggregated portfolio.
    """
    nav_series = []
    for name, spec in strategies.items():
        print(f"Running strategy: {name}")
        bt_mod = importlib.import_module(spec["path"])
        bt_result = bt_mod.run_strategy()
        nav = pd.Series(
            [row["value"] for row in bt_result.log_data],
            index=pd.to_datetime([row["date"] for row in bt_result.log_data]),
            name=name,
            dtype=float,
        ).sort_index()
        nav_series.append(nav)

    weights = pd.Series({name: spec["weight"] for name, spec in strategies.items()}, dtype=float)
    weights /= weights.sum()

    nav_df = pd.concat(nav_series, axis=1).dropna().sort_index()

    positions = initial_cash * leverage * weights / nav_df.iloc[0]
    cash = initial_cash - (positions * nav_df.iloc[0]).sum()

    dates = nav_df.index
    daily_nav = []

    for i, (date, prices) in enumerate(nav_df.iterrows()):
        if i > 0 and date.year != dates[i - 1].year:
            portfolio_nav = (positions * prices).sum() + cash
            positions = portfolio_nav * leverage * weights / prices
            cash = portfolio_nav - (positions * prices).sum()

        portfolio_nav = (positions * prices).sum() + cash
        daily_nav.append(portfolio_nav)

    daily_nav_df = pd.Series(daily_nav, index=dates, name="Portfolio NAV")
    return daily_nav_df


def generate_reports(daily_nav_df: pd.Series, reports: Path) -> None:
    """Print performance summary and save standard backtest plots and metrics."""
    reports.mkdir(exist_ok=True)

    mdd, mdd_dur = pwb_perf.max_drawdown(daily_nav_df)
    metrics = {
        "Final NAV": float(daily_nav_df.iloc[-1]),
        "Total Return": float(pwb_perf.total_return(daily_nav_df)),
        "CAGR": float(pwb_perf.cagr(daily_nav_df)),
        "Annualized Volatility": float(pwb_perf.annualized_volatility(daily_nav_df)),
        "Max Drawdown": float(mdd),
        "Max DD Duration": str(mdd_dur),
        "Ulcer Index": float(pwb_perf.ulcer_index(daily_nav_df)),
        "Sharpe Ratio": float(pwb_perf.sharpe_ratio(daily_nav_df)),
        "Sortino Ratio": float(pwb_perf.sortino_ratio(daily_nav_df)),
        "Calmar Ratio": float(pwb_perf.calmar_ratio(daily_nav_df)),
    }

    print("Performance Summary:")
    print(f"Final NAV:               {metrics['Final NAV']:.2f}")
    print(f"Total Return:            {metrics['Total Return']:.2%}")
    print(f"CAGR:                    {metrics['CAGR']:.2%}")
    print(f"Annualized Volatility:   {metrics['Annualized Volatility']:.2%}")
    print(f"Max Drawdown:            {metrics['Max Drawdown']:.2%}")
    print(f"Max DD Duration:         {metrics['Max DD Duration']}")
    print(f"Ulcer Index:             {metrics['Ulcer Index']:.4f}")
    print(f"Sharpe Ratio:            {metrics['Sharpe Ratio']:.3f}")
    print(f"Sortino Ratio:           {metrics['Sortino Ratio']:.3f}")
    print(f"Calmar Ratio:            {metrics['Calmar Ratio']:.3f}")

    returns_table = pwb_perf.returns_table(daily_nav_df)
    print(returns_table)

    with open(reports / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)
    returns_table.to_csv(reports / "returns_table.csv")

    pwb_perf.plot_equity_curve(daily_nav_df).figure.savefig(reports / "equity_curve.png")
    pwb_perf.plot_return_heatmap(daily_nav_df).figure.savefig(reports / "return_heatmap.png")
    pwb_perf.plot_underwater(daily_nav_df).figure.savefig(reports / "underwater.png")
    pwb_perf.plot_rolling_sharpe(daily_nav_df).figure.savefig(reports / "rolling_sharpe.png")
