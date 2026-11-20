"""A synthetic long-short book whose NAV is pinned bit for bit (``tests/data``).

``tests/test_short_borrow.py`` checks that ``short_borrow_bps=0`` -- and no
argument at all -- leaves this NAV exactly as ``origin/main`` produced it
before the borrow charge existed (``short_borrow_nav_reference.json``, the
floats written with ``float.hex``). Two runs: a plain list of names, and the
``pit_exit="hold"`` book of ``test_pit_hold_accounting.py`` that is short a
name while it is out of the universe (the harness marks it through the cash).
"""

import numpy as np

from pwb_toolbox.backtesting import BaseStrategy
from pwb_toolbox.backtesting import backtest_engine as be

from _synthetic import offline, panel

N = 260
NAMES = ("A", "B", "C", "D", "E", "F")


def prices():
    rng = np.random.default_rng(11)
    return panel({
        s: 100 * np.exp(np.cumsum(rng.normal(0.0002 * (i - 2.5), 0.012, N)))
        for i, s in enumerate(NAMES)
    })


class LongShortBook(BaseStrategy):
    """Every 21 bars: long the three best names of the last 21 bars, short the three worst."""

    params = (("indicator_cls", None), ("indicator_kwargs", {}), ("gross", 0.9))

    def __init__(self):
        super().__init__()
        self.pbar.disable = True

    def next(self):
        super().next()
        i = len(self) - 1
        if i < 21 or i % 21:
            return
        ranked = sorted(self.datas, key=lambda d: d.close[0] / d.close[-21])
        w = self.p.gross / len(ranked)
        for d in ranked[:3]:
            self.order_target_percent(d, -w)
        for d in ranked[3:]:
            self.order_target_percent(d, w)


def run_book(**kwargs):
    with offline(prices()):
        return be.run_strategy(
            indicator_cls=None,
            indicator_kwargs={},
            strategy_cls=LongShortBook,
            strategy_kwargs={},
            symbols=list(NAMES),
            start_date="2020-01-01",
            cash=100_000.0,
            broker_kwargs={"commission": 0.0005},
            **kwargs,
        )


def nav(strategy):
    return [row["value"] for row in strategy.log_data]
