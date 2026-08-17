"""AST node types for the PineScript subset this package understands."""

from dataclasses import dataclass, field
from typing import Any

# --- expressions -------------------------------------------------------------


@dataclass(frozen=True)
class Num:
    value: float


@dataclass(frozen=True)
class Str:
    value: str


@dataclass(frozen=True)
class Bool:
    value: bool


@dataclass(frozen=True)
class Na:
    """Pine's ``na``, the missing-value literal."""


@dataclass(frozen=True)
class ListLit:
    """A bracketed list, as in ``options=["EMA", "SMA"]``.

    Pine calls these arrays. Nothing here builds one; they turn up as the
    ``options`` of an input, where they describe a dropdown and say nothing
    about how the strategy trades.
    """

    items: tuple = ()


@dataclass(frozen=True)
class Name:
    """An identifier, possibly dotted (``close``, ``ta.sma``, ``strategy.long``)."""

    id: str


@dataclass(frozen=True)
class Index:
    """Historical access: ``close[1]`` is the previous bar's close."""

    base: Any
    offset: Any


@dataclass(frozen=True)
class Call:
    func: str
    args: tuple = ()
    kwargs: tuple = ()  # ((name, expr), ...) -- a tuple so the node stays hashable


@dataclass(frozen=True)
class Unary:
    op: str
    operand: Any


@dataclass(frozen=True)
class Binary:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Ternary:
    cond: Any
    then: Any
    other: Any


# --- statements --------------------------------------------------------------


@dataclass
class Assign:
    target: str
    value: Any
    #: ``""`` for a plain assignment, ``var``/``varip`` for persistent ones,
    #: ``:=`` for reassignment of an existing variable.
    qualifier: str = ""


@dataclass
class TupleAssign:
    """``[macd, signal, hist] = ta.macd(...)`` -- parsed so it can be reported."""

    targets: list
    value: Any


@dataclass
class If:
    cond: Any
    body: list
    orelse: list = field(default_factory=list)


@dataclass
class ExprStmt:
    value: Any


@dataclass
class Unsupported:
    """A construct parsed only well enough to be skipped and reported."""

    kind: str
    text: str


@dataclass
class Program:
    #: ``("strategy" | "indicator", title)`` when the script declares one.
    declaration: tuple | None
    version: int | None
    body: list
