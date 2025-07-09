from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Callable, Dict, Iterable, List, Sequence

import pandas as pd

from ...datasets import load_dataset


class UniverseSelectionModel(ABC):
    """Base class for universe selection models."""

    @abstractmethod
    def symbols(self, as_of: date | str | None = None) -> List[str]:
        """Return the active list of symbols."""
        raise NotImplementedError


class ManualUniverseSelectionModel(UniverseSelectionModel):
    """Universe defined by a static list of tickers."""

    def __init__(self, symbols: Sequence[str]):
        self._symbols = list(symbols)

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        return list(self._symbols)


class ScheduledUniverseSelectionModel(UniverseSelectionModel):
    """Switch universe based on a schedule of dates."""

    def __init__(self, schedule: Dict[date | str, Sequence[str]]):
        self.schedule = {
            (pd.Timestamp(k).date() if not isinstance(k, date) else k): list(v)
            for k, v in schedule.items()
        }

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        if not self.schedule:
            return []
        dt = pd.Timestamp(as_of or date.today()).date()
        valid = [d for d in self.schedule if d <= dt]
        if not valid:
            return []
        last = max(valid)
        return self.schedule[last]


class CoarseFundamentalUniverseSelectionModel(UniverseSelectionModel):
    """Universe filtered using coarse fundamental data."""

    def __init__(
        self,
        selector: Callable[[pd.DataFrame], Iterable[str]],
        dataset: str = "Stocks-Quarterly-BalanceSheet",
    ):
        self.selector = selector
        self.dataset = dataset

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset(self.dataset)
        return list(self.selector(df))


class FineFundamentalUniverseSelectionModel(UniverseSelectionModel):
    """Universe filtered using fine fundamental data."""

    def __init__(
        self,
        selector: Callable[[pd.DataFrame], Iterable[str]],
        dataset: str = "Stocks-Quarterly-Earnings",
    ):
        self.selector = selector
        self.dataset = dataset

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset(self.dataset)
        return list(self.selector(df))


class ETFConstituentsUniverseSelectionModel(UniverseSelectionModel):
    """Universe containing constituents of a given ETF."""

    def __init__(self, etf: str):
        self.etf = etf

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset("ETF-Constituents")
        if "etf" in df.columns:
            col = "etf"
        else:
            col = df.columns[0] if df.columns else "etf"
        if df.empty:
            return []
        return list(df[df[col] == self.etf]["symbol"].unique())


class IndexConstituentsUniverseSelectionModel(UniverseSelectionModel):
    """Universe of constituents for a specified index."""

    def __init__(self, index: str):
        self.index = index

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset("Index-Constituents")
        if df.empty:
            return []
        col = "index" if "index" in df.columns else df.columns[0]
        return list(df[df[col] == self.index]["symbol"].unique())


class OptionUniverseSelectionModel(UniverseSelectionModel):
    """Universe consisting of options for the given underlyings."""

    def __init__(self, underlying_symbols: Sequence[str]):
        self.underlyings = list(underlying_symbols)

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        return list(self.underlyings)


class ADRUniverseSelectionModel(UniverseSelectionModel):
    """Universe of American Depositary Receipts."""

    def __init__(self, dataset: str = "ADR-Listings"):
        self.dataset = dataset

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset(self.dataset)
        if df.empty:
            return []
        return list(df["symbol"].unique())


class CryptoUniverseSelectionModel(UniverseSelectionModel):
    """Universe built from cryptocurrency tickers."""

    def __init__(self, top_n: int | None = None):
        self.top_n = top_n

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        df = load_dataset("Cryptocurrencies-Daily-Price")
        syms = list(dict.fromkeys(df["symbol"]))
        if self.top_n is not None:
            syms = syms[: self.top_n]
        return syms


class UniverseSelectionModelChain(UniverseSelectionModel):
    """Combine multiple universe selection models."""

    def __init__(self, models: Iterable[UniverseSelectionModel]):
        self.models = list(models)

    def symbols(self, as_of: date | str | None = None) -> List[str]:
        all_syms: List[str] = []
        for m in self.models:
            all_syms.extend(m.symbols(as_of))
        seen = set()
        uniq = []
        for s in all_syms:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq


__all__ = [
    "UniverseSelectionModel",
    "ManualUniverseSelectionModel",
    "ScheduledUniverseSelectionModel",
    "CoarseFundamentalUniverseSelectionModel",
    "FineFundamentalUniverseSelectionModel",
    "ETFConstituentsUniverseSelectionModel",
    "IndexConstituentsUniverseSelectionModel",
    "OptionUniverseSelectionModel",
    "ADRUniverseSelectionModel",
    "CryptoUniverseSelectionModel",
    "UniverseSelectionModelChain",
]

