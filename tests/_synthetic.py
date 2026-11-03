"""Synthetic price panels and a patched loader, so ``run_strategy`` runs offline.

Nothing here touches the Hub: ``get_pricing`` is replaced by a function that
returns the panel it was given, and every test passes a flat ``commission`` in
``broker_kwargs``, which skips the measured per-symbol cost tables.
"""

from contextlib import contextmanager
from unittest import mock

import numpy as np
import pandas as pd

import pwb_toolbox.datasets as pwb_ds


def panel(closes: dict, start="2020-01-01", opens=None) -> pd.DataFrame:
    """``(symbol, field)`` panel from ``{symbol: closes}``; NaN closes are absent rows.

    The open of a bar is the previous close unless ``opens`` says otherwise, so a
    target sized on today's close fills at exactly that price tomorrow.
    """
    n = len(next(iter(closes.values())))
    index = pd.bdate_range(start, periods=n)
    frames = {}
    for symbol, close in closes.items():
        close = np.asarray(close, dtype=float)
        if opens and symbol in opens:
            open_ = np.asarray(opens[symbol], dtype=float)
        else:
            open_ = np.concatenate([[close[0]], close[:-1]])
            # an absent row stays absent; the first bar after a hole opens at its close
            gap = np.isnan(open_) & ~np.isnan(close)
            open_[gap] = close[gap]
            open_[np.isnan(close)] = np.nan
        frames[symbol] = pd.DataFrame(
            {
                "open": open_,
                "high": np.fmax(open_, close),
                "low": np.fmin(open_, close),
                "close": close,
            },
            index=index,
        )
    out = pd.concat(frames, axis=1)
    out.columns.names = [None, None]
    return out


@contextmanager
def offline(prices: pd.DataFrame):
    """Make ``run_strategy`` load ``prices`` instead of the Hub."""
    with mock.patch.object(pwb_ds, "get_pricing", lambda *a, **k: prices.copy()):
        yield
