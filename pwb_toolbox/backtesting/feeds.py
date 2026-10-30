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
"""

from __future__ import annotations

import numpy as np
import backtrader as bt
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
