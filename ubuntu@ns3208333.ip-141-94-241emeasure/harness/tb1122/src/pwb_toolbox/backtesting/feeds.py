"""A pandas feed that reads its bars from numpy arrays.

``bt.feeds.PandasData._load`` fetches every field of every bar with
``DataFrame.iloc[idx, col]``, five or six scalar lookups per bar and per feed,
each one a full pandas indexing call. Profiled on a 1 941-symbol point-in-time
universe over 6 010 bars, those lookups were 826 s of a 1 274 s ``cerebro.run``;
on a 50-symbol strategy, 39 s of 60. The engine does nothing with the frame
but read it in order, so the columns are pulled into float arrays once, at
``start()``, and the datetime column is converted once. Measured on synthetic
data, 100 and 500 feeds over 5 000 bars, with a monthly rebalancing strategy:
2.7 to 2.8 times faster, final NAV identical to the last cent.

Everything else -- column mapping, the ``datetime`` parameter, ``fromdate`` /
``todate`` filtering done by the base class in ``_load``'s callers -- is
inherited unchanged.

The speed-up exists for backtrader only. Tradewind's ``PandasData`` already
reads its bars from arrays, and none of the internals patched below exist
there, so on that engine ``ArrayPandasData`` *is* ``bt.feeds.PandasData``.

Which engine is running is told by its module name, and by nothing else.
From 0.1.42 to 0.1.49 the test was ``hasattr(bt.feeds.PandasData,
"_colmapping")``; ``_colmapping`` is set on each feed in ``__init__``, never on
the class, so the test was always false and every backtest ran on the plain
``PandasData``. Measured on 0.1.49 (12 Nov 2026), restoring this class: the
engine of a ``sp500`` point-in-time strategy 1 242 -> 300 s, the whole run
x3.4 (fundamentals strategy x2.6, 7-ETF strategy x1.6), Sharpe and final NAV
identical to the cent.
"""

from __future__ import annotations

import numpy as np

from ..engine import load as _load_engine

bt = _load_engine()  # backtrader by default, Tradewind on request; see pwb_toolbox.engine

if bt.__name__ != "backtrader":
    ArrayPandasData = bt.feeds.PandasData
else:
    from backtrader.utils.date import date2num

    class ArrayPandasData(bt.feeds.PandasData):
        """``PandasData`` with the frame flattened into arrays at ``start()``."""

        def start(self):
            super().start()
            frame = self.p.dataname
            self._pwb_arrays = {}
            for datafield in self.getlinealiases():
                if datafield == "datetime":
                    continue
                colindex = self._colmapping[datafield]
                if colindex is None:
                    continue
                self._pwb_arrays[datafield] = frame.iloc[:, colindex].to_numpy(dtype=float)
            coldtime = self._colmapping["datetime"]
            stamps = frame.index if coldtime is None else frame.iloc[:, coldtime]
            self._pwb_dtnum = np.fromiter(
                (date2num(stamp.to_pydatetime()) for stamp in stamps), dtype=float, count=len(frame)
            )
            self._pwb_len = len(frame)

        def _load(self):
            self._idx += 1
            idx = self._idx
            if idx >= self._pwb_len:
                return False
            lines = self.lines
            for datafield, values in self._pwb_arrays.items():
                getattr(lines, datafield)[0] = values[idx]
            lines.datetime[0] = self._pwb_dtnum[idx]
            return True
