from typing import List
import pandas as pd
import pwb_toolbox.datasets as pwb_ds


def get_most_liquid_symbols(n: int = 1_200, as_of=None) -> List[str]:
    """The `n` most liquid stock symbols, by median dollar volume.

    With ``as_of``, the ranking as it stood on that date. Without it, every
    symbol that was in the top ``n`` at any point -- which is what a backtest
    spanning several years has to load.

    This used to rank on the **last** bar of the dataset and replay that
    ranking over the whole history, which held the winners of today back to
    2003 and never held the names that mattered then and have since died. The
    ranking is now point-in-time (see ``datasets.pit_universe``).

    Note what the no-``as_of`` form does *not* do: returning the union widens
    the load correctly but does not keep each name to its own window. A
    strategy that wants the membership enforced per date should load through
    ``symbols=["sp500"]``, which applies it, or call this per rebalance date.
    """
    from pwb_toolbox.datasets.pit_universe import load_pit_universe, pit_symbols

    if as_of is None:
        return pit_symbols(n)

    universe = load_pit_universe(n)
    as_of = pd.Timestamp(as_of)
    upto = universe[universe["date"] <= as_of]
    if upto.empty:
        return []
    # the last session at or before as_of -- not the whole history up to it
    latest = upto[upto["date"] == upto["date"].max()]
    return latest.sort_values("rank")["symbol"].tolist()[:n]


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
