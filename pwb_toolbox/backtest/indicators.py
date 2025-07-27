import backtrader as bt
import numpy as np


class CompositeIndicator(bt.Indicator):
    lines = ("long",)
    params = dict(
        indicators=[],
        weights=[],
    )

    def __init__(self):
        self.indicators = []
        for indicator in self.p.indicators:
            signal = indicator["signal"]
            signal_kwargs = indicator["signal_kwargs"]
            self.indicators.append(signal(self.data.close, **signal_kwargs))

    def next(self):
        long_scores = np.mean(
            [ind[0] * weight for ind, weight in zip(self.indicators, self.p.weights)]
        )
        self.lines.long[0] = long_scores
