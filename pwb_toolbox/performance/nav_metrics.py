import json
from pathlib import Path
from typing import Dict

import pandas as pd

from . import (
    total_return,
    cagr,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
)


def _compute_metrics(nav: pd.Series) -> Dict[str, float]:
    """Compute key performance metrics for a NAV series."""
    return {
        "total_return": total_return(nav),
        "cagr": cagr(nav),
        "annualized_volatility": annualized_volatility(nav),
        "max_drawdown": max_drawdown(nav)[0],
        "sharpe_ratio": sharpe_ratio(nav),
    }


def main(csv_path: str | Path) -> None:
    """Load a NAV CSV and print metrics as JSON."""
    df = pd.read_csv(csv_path, comment="#", parse_dates=[0], index_col=0)
    nav = df.iloc[:, 0]

    results: Dict[str, Dict[str, float]] = {"all": _compute_metrics(nav)}

    today = nav.index[-1]
    start_of_year = pd.Timestamp(year=today.year, month=1, day=1)
    results["ytd"] = _compute_metrics(nav[nav.index >= start_of_year])
    results["last_30d"] = _compute_metrics(nav[nav.index >= today - pd.Timedelta(days=30)])

    print(json.dumps(results, indent=2, default=float))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = (
            Path(__file__).resolve().parent.parent
            / "strategies"
            / "ib"
            / "logs"
            / "sample_nav_history.csv"
        )
    main(path)
