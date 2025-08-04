from typing import List
import pandas as pd
import pwb_toolbox.datasets as pwb_ds


def get_most_liquid_symbols(n: int = 1_200) -> List[str]:
    """Return the `n` most liquid stock symbols (volume × price on last bar)."""
    df = pwb_ds.load_dataset("Stocks-Daily-Price", adjust=True, extend=True)
    last_date = df["date"].max()
    today = df[df["date"] == last_date].copy()
    today["liquidity"] = today["volume"] * today["close"]
    liquid = today.sort_values("liquidity", ascending=False)
    return liquid["symbol"].tolist()[:n]


def get_least_volatile_symbols(symbols=["sp500"], start="1990-01-01") -> List[str]:
    pivot = pwb_ds.get_pricing(
        symbol_list=symbols,
        fields=["open", "high", "low", "close"],
        start_date=start,
        extend=True,
    )
    td = pd.bdate_range(pivot.index.min(), pivot.index.max())
    pivot = pivot.reindex(td).ffill().bfill()
    symbols = []
    for sym in pivot.columns.levels[0]:
        df = (
            pivot[sym]
            .copy()
            .reset_index()
            .rename(columns={"index": "date"})
            .set_index("date")
        )
        if df.close.pct_change().abs().max() > 3:  # same volatility filter
            continue
        symbols.append(sym)
    return symbols
