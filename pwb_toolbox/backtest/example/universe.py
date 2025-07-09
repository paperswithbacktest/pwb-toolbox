from __future__ import annotations

from typing import Iterable, List

from ...datasets import SP500_SYMBOLS


class Universe:
    """Base universe."""

    def symbols(self) -> List[str]:
        raise NotImplementedError


class StaticUniverse(Universe):
    """Always return the provided list of tickers."""

    def __init__(self, symbols: Iterable[str]):
        self._symbols = list(symbols)

    def symbols(self) -> List[str]:
        return self._symbols


class SP500Universe(Universe):
    """Universe containing current S&P 500 constituents."""

    def symbols(self) -> List[str]:
        return SP500_SYMBOLS
