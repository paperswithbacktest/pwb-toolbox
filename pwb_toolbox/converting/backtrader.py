"""Generate a Backtrader strategy from a parsed PineScript program.

The structural problem
----------------------

Pine and Backtrader disagree about when a computation happens. In Pine every
expression is a series evaluated on every bar, so ``ta.sma(close, 20)`` can be
written anywhere. In Backtrader an indicator is a line object built once in
``__init__`` and then *indexed* per bar in ``next``.

So the translation is a hoist: every recognised ``ta.*`` call becomes a named
attribute constructed in ``__init__``, and every reference to it in a condition
becomes ``self.<name>[0]``. That is the whole trick, and it is why an
expression is lowered differently depending on which of the two contexts it
lands in -- see :meth:`_Generator._line_expr` and :meth:`_Generator._value_expr`.

What is deliberately not translated
-----------------------------------

Anything whose Backtrader equivalent would be a guess is reported rather than
emitted: multi-timeframe ``request.security``, ``var``/``varip`` persistence,
arrays and matrices, user-defined functions, loops, and ``strategy.exit`` with
stops or limits attached. Presentational calls (``plot``, ``bgcolor``,
``label.new``) are dropped, but reported separately as *ignored* -- they change
nothing about how the strategy trades.

A conversion with a non-empty ``unsupported`` list is not a working port. It is
a starting point plus a list of what you still have to write yourself.
"""

import keyword
import re
from dataclasses import dataclass, field
from typing import Any

from .nodes import (
    Assign,
    Binary,
    Bool,
    Call,
    ExprStmt,
    If,
    Index,
    Na,
    Name,
    Num,
    Str,
    Ternary,
    TupleAssign,
    Unary,
    Unsupported,
)
from .parser import PineSyntaxError, parse


@dataclass(frozen=True)
class IndicatorSpec:
    """How a Pine indicator maps onto a Backtrader one."""

    bt_name: str
    #: Pine's first positional argument is the source series.
    takes_source: bool = True
    #: Source to use when Pine's short form omits it (``ta.highest(20)``).
    default_source: str = "close"
    #: Pine passes a length that becomes Backtrader's ``period``.
    takes_period: bool = True


INDICATORS = {
    "ta.sma": IndicatorSpec("SMA"),
    "ta.ema": IndicatorSpec("EMA"),
    "ta.wma": IndicatorSpec("WMA"),
    "ta.rma": IndicatorSpec("SmoothedMovingAverage"),
    "ta.rsi": IndicatorSpec("RSI"),
    "ta.stdev": IndicatorSpec("StandardDeviation"),
    "ta.highest": IndicatorSpec("Highest", default_source="high"),
    "ta.lowest": IndicatorSpec("Lowest", default_source="low"),
    "ta.atr": IndicatorSpec("ATR", takes_source=False),
    "ta.tr": IndicatorSpec("TrueRange", takes_source=False, takes_period=False),
}

#: Pine cross helpers, mapped to a CrossOver line plus the comparison that
#: recovers the direction Pine means.
CROSSES = {
    "ta.crossover": "> 0",
    "ta.crossunder": "< 0",
    "ta.cross": "!= 0",
}

PRICE_SERIES = {
    "open": "self.data.open",
    "high": "self.data.high",
    "low": "self.data.low",
    "close": "self.data.close",
    "volume": "self.data.volume",
}

#: Pine's derived price series, which Backtrader has no line for.
DERIVED_SERIES = {
    "hl2": "(self.data.high[{i}] + self.data.low[{i}]) / 2",
    "hlc3": "(self.data.high[{i}] + self.data.low[{i}] + self.data.close[{i}]) / 3",
    "ohlc4": (
        "(self.data.open[{i}] + self.data.high[{i}] "
        "+ self.data.low[{i}] + self.data.close[{i}]) / 4"
    ),
}

INPUT_FUNCS = {
    "input",
    "input.int",
    "input.float",
    "input.bool",
    "input.string",
    "input.source",
    "input.timeframe",
}

#: Presentational calls: dropped from the output, reported as ignored.
PRESENTATIONAL = {
    "plot",
    "plotshape",
    "plotchar",
    "plotarrow",
    "plotcandle",
    "plotbar",
    "bgcolor",
    "barcolor",
    "hline",
    "fill",
    "alert",
    "alertcondition",
    "label.new",
    "line.new",
    "box.new",
    "table.new",
    "table.cell",
}

#: Namespaces holding nothing but drawing constants -- `color.green`,
#: `shape.triangleup`, `location.belowbar`. They reach the generator only when
#: a script names one before handing it to a plot, and a plot is dropped, so
#: none of them can change how a strategy trades.
PRESENTATIONAL_NAMESPACES = (
    "color.",
    "display.",
    "extend.",
    "font.",
    "format.",
    "hline.",
    "label.style_",
    "line.style_",
    "location.",
    "plot.style_",
    "position.",
    "scale.",
    "shape.",
    "size.",
    "text.",
    "xloc.",
    "yloc.",
)


def _presentational_constant(name: str) -> bool:
    """True for a drawing constant such as ``color.green``."""
    return name.startswith(PRESENTATIONAL_NAMESPACES)


_BINARY_OPS = {
    "and": "and",
    "or": "or",
    "==": "==",
    "!=": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "+": "+",
    "-": "-",
    "*": "*",
    "/": "/",
    "%": "%",
}

#: Attribute names already meaningful on a ``bt.Strategy``.
_RESERVED = {
    "data",
    "datas",
    "broker",
    "p",
    "params",
    "position",
    "next",
    "buy",
    "sell",
    "close",
    "order",
    "env",
    "cerebro",
    "lines",
}


class ConversionError(RuntimeError):
    """Raised when the source cannot be converted at all."""


@dataclass
class ConversionResult:
    code: str
    class_name: str
    params: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)
    ignored: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing needing attention was left behind.

        Ignored presentational calls do not count -- dropping a ``plot`` does
        not change how the strategy trades.
        """
        return not self.unsupported


def _class_name(title: str, fallback: str = "ConvertedStrategy") -> str:
    parts = re.findall(r"[A-Za-z0-9]+", title or "")
    name = "".join(part[:1].upper() + part[1:] for part in parts)
    if not name or name[0].isdigit():
        return fallback
    return name


def _safe(name: str) -> str:
    if keyword.iskeyword(name) or name in _RESERVED or name.startswith("_"):
        return f"pine_{name}"
    return name


def _literal(node) -> Any:
    if isinstance(node, Num):
        value = node.value
        return int(value) if value == int(value) else value
    if isinstance(node, Str):
        return node.value
    if isinstance(node, Bool):
        return node.value
    return None


class _Generator:
    def __init__(self, program, class_name=None):
        self.program = program
        self.declaration = program.declaration
        title = self.declaration[1] if self.declaration else ""
        self.class_name = class_name or _class_name(title)
        self.params = []  # (pine_name, default)
        self.param_names = set()
        self.series = {}  # pine name -> attribute name in __init__
        self.scalars = set()  # names computed as locals in next()
        self.init_lines = []
        self.next_lines = []
        self.unsupported = []
        self.ignored = []
        self._counter = 0
        self._hoisted = {}  # construction source -> attribute name

    # --- helpers -------------------------------------------------------------

    def _fresh(self, stem):
        self._counter += 1
        return f"_{stem}_{self._counter}"

    def _hoist(self, stem, construction):
        """Build ``construction`` in ``__init__`` once, returning its handle.

        Identical constructions are shared. Backtrader recomputes every
        indicator on every bar, so emitting the same CrossOver twice -- which
        ``ta.crossover``/``ta.crossunder`` on one pair otherwise does -- would
        double that work for no benefit.
        """
        attr = self._hoisted.get(construction)
        if attr is None:
            attr = self._fresh(stem)
            self._hoisted[construction] = attr
            self.init_lines.append(f"self.{attr} = {construction}")
        return f"self.{attr}"

    def _reject(self, message):
        if message not in self.unsupported:
            self.unsupported.append(message)

    def _ignore(self, message):
        if message not in self.ignored:
            self.ignored.append(message)

    # --- expression lowering -------------------------------------------------

    def _line_expr(self, node):
        """Lower an expression for ``__init__``, where values are line objects.

        Returns ``None`` when the expression cannot be expressed as a line.
        """
        if isinstance(node, Name):
            if node.id in PRICE_SERIES:
                return PRICE_SERIES[node.id]
            if node.id in self.series:
                return f"self.{self.series[node.id]}"
            if node.id in self.param_names:
                return f"self.p.{_safe(node.id)}"
            return None
        if isinstance(node, Num):
            return repr(_literal(node))
        if isinstance(node, Call):
            return self._hoist_indicator(node)
        return None

    def _hoist_indicator(self, call):
        """Build a Backtrader indicator in ``__init__`` and return its handle."""
        spec = INDICATORS.get(call.func)
        if spec is None:
            return None

        args = list(call.args)
        source_code = None
        if spec.takes_source:
            if len(args) >= 2 or (len(args) == 1 and not spec.takes_period):
                source_code = self._line_expr(args.pop(0))
            else:
                source_code = PRICE_SERIES[spec.default_source]
            if source_code is None:
                self._reject(
                    f"{call.func}: source argument is not a plain series or parameter"
                )
                return None
        else:
            source_code = "self.data"

        pieces = [source_code]
        if spec.takes_period:
            period = None
            if args:
                period = self._line_expr(args.pop(0))
            for key, value in call.kwargs:
                if key in ("length", "period"):
                    period = self._line_expr(value)
            if period is None:
                self._reject(f"{call.func}: could not resolve its length argument")
                return None
            pieces.append(f"period={period}")

        return self._hoist(
            spec.bt_name.lower(),
            f"bt.indicators.{spec.bt_name}({', '.join(pieces)})",
        )

    def _value_expr(self, node):
        """Lower an expression for ``next()``, where values are numbers."""
        if isinstance(node, Num):
            return repr(_literal(node))
        if isinstance(node, Str):
            return repr(node.value)
        if isinstance(node, Bool):
            return "True" if node.value else "False"
        if isinstance(node, Na):
            self._ignore("na literal converted to float('nan')")
            return "float('nan')"

        if isinstance(node, Name):
            return self._value_name(node.id, 0)

        if isinstance(node, Index):
            offset = _literal(node.offset)
            if not isinstance(node.base, Name) or not isinstance(offset, int):
                self._reject("history access is only supported as name[constant]")
                return "None"
            return self._value_name(node.base.id, -offset)

        if isinstance(node, Unary):
            operand = self._value_expr(node.operand)
            return f"(not {operand})" if node.op == "not" else f"({node.op}{operand})"

        if isinstance(node, Binary):
            op = _BINARY_OPS.get(node.op)
            if op is None:
                self._reject(f"operator {node.op!r} is not supported")
                return "None"
            return (
                f"({self._value_expr(node.left)} {op} {self._value_expr(node.right)})"
            )

        if isinstance(node, Ternary):
            return (
                f"({self._value_expr(node.then)} if {self._value_expr(node.cond)} "
                f"else {self._value_expr(node.other)})"
            )

        if isinstance(node, Call):
            return self._value_call(node)

        self._reject(f"expression of type {type(node).__name__} is not supported")
        return "None"

    def _value_name(self, name, index):
        if name in PRICE_SERIES:
            return f"{PRICE_SERIES[name]}[{index}]"
        if name in DERIVED_SERIES:
            return DERIVED_SERIES[name].format(i=index)
        if name in self.series:
            return f"self.{self.series[name]}[{index}]"
        if name in self.param_names:
            if index:
                self._reject(f"{name}: a parameter has no bar history")
            return f"self.p.{_safe(name)}"
        if name in self.scalars:
            if index:
                self._reject(
                    f"{name}: history of a computed value needs a Backtrader line"
                )
            return _safe(name)
        if name == "bar_index":
            return "len(self)"
        if _presentational_constant(name):
            # `col = up ? color.green : color.red` only ever feeds a plot, and
            # plots are dropped. Refusing the colour would report the strategy
            # as unconvertible over something that cannot affect a trade.
            self._ignore(f"{name} dropped: presentational only")
            return "None"
        self._reject(f"unknown identifier {name!r}")
        return "None"

    def _value_call(self, call):
        if call.func in CROSSES:
            if len(call.args) != 2:
                self._reject(f"{call.func} expects two arguments")
                return "None"
            left = self._line_expr(call.args[0])
            right = self._line_expr(call.args[1])
            if left is None or right is None:
                self._reject(f"{call.func}: arguments must be series or parameters")
                return "None"
            handle = self._hoist("cross", f"bt.indicators.CrossOver({left}, {right})")
            return f"({handle}[0] {CROSSES[call.func]})"

        if call.func in INDICATORS:
            handle = self._hoist_indicator(call)
            return f"{handle}[0]" if handle else "None"

        if call.func == "ta.change":
            source = call.args[0] if call.args else Name("close")
            length = _literal(call.args[1]) if len(call.args) > 1 else 1
            if not isinstance(length, int):
                self._reject("ta.change: length must be a constant")
                return "None"
            now = self._value_expr(source)
            before = self._value_expr(
                Index(base=source, offset=Num(float(length)))
                if isinstance(source, Name)
                else source
            )
            return f"({now} - {before})"

        if call.func in ("math.abs", "math.max", "math.min", "math.round"):
            mapped = {
                "math.abs": "abs",
                "math.max": "max",
                "math.min": "min",
                "math.round": "round",
            }[call.func]
            inner = ", ".join(self._value_expr(a) for a in call.args)
            return f"{mapped}({inner})"

        if call.func == "nz":
            inner = self._value_expr(call.args[0]) if call.args else "0"
            fallback = self._value_expr(call.args[1]) if len(call.args) > 1 else "0"
            return f"({inner} if {inner} == {inner} else {fallback})"

        self._reject(f"call to {call.func}() is not supported")
        return "None"

    # --- statements ----------------------------------------------------------

    def _collect_input(self, statement):
        call = statement.value
        default = None
        for arg in call.args:
            literal = _literal(arg)
            if literal is not None and not isinstance(literal, str):
                default = literal
                break
        if default is None and call.args:
            default = _literal(call.args[0])
        for key, value in call.kwargs:
            if key == "defval":
                default = _literal(value)
        if call.func == "input.bool" and isinstance(default, (int, float)):
            default = bool(default)
        self.params.append((statement.target, default))
        self.param_names.add(statement.target)

    def _emit_statement(self, statement, indent):
        pad = "    " * indent

        if isinstance(statement, Unsupported):
            self._reject(f"{statement.kind} block is not supported")
            return

        if isinstance(statement, TupleAssign):
            self._reject(
                "tuple destructuring (e.g. [macd, signal, hist] = ta.macd(...)) "
                "is not supported"
            )
            return

        if isinstance(statement, Assign):
            self._emit_assign(statement, indent, pad)
            return

        if isinstance(statement, If):
            cond = self._value_expr(statement.cond)
            self.next_lines.append(f"{pad}if {cond}:")
            body = list(statement.body)
            emitted = len(self.next_lines)
            for inner in body:
                self._emit_statement(inner, indent + 1)
            if len(self.next_lines) == emitted:
                self.next_lines.append(f"{pad}    pass")
            if statement.orelse:
                self.next_lines.append(f"{pad}else:")
                emitted = len(self.next_lines)
                for inner in statement.orelse:
                    self._emit_statement(inner, indent + 1)
                if len(self.next_lines) == emitted:
                    self.next_lines.append(f"{pad}    pass")
            return

        if isinstance(statement, ExprStmt):
            self._emit_expr_statement(statement.value, pad)
            return

        self._reject(f"statement of type {type(statement).__name__} is not supported")

    def _emit_assign(self, statement, indent, pad):
        if statement.qualifier in ("var", "varip"):
            self._reject(
                f"{statement.qualifier} {statement.target}: persistent variables "
                "need explicit state on the Backtrader strategy"
            )
            return

        if isinstance(statement.value, Call) and statement.value.func in INPUT_FUNCS:
            if indent:
                self._reject(
                    f"{statement.target}: inputs must be declared at top level"
                )
                return
            self._collect_input(statement)
            return

        # A bare indicator call becomes a line object built once in __init__.
        if isinstance(statement.value, Call) and statement.value.func in INDICATORS:
            handle = self._hoist_indicator(statement.value)
            if handle is not None:
                self.series[statement.target] = handle[len("self.") :]
            return

        if statement.qualifier == ":=" and statement.target not in self.scalars:
            self._reject(
                f"{statement.target}: reassignment of a value that was not "
                "defined in this scope"
            )
            return

        value = self._value_expr(statement.value)
        self.scalars.add(statement.target)
        self.next_lines.append(f"{pad}{_safe(statement.target)} = {value}")

    def _emit_expr_statement(self, expr, pad):
        if not isinstance(expr, Call):
            self._reject("a bare expression statement has no Backtrader equivalent")
            return

        if expr.func in PRESENTATIONAL:
            self._ignore(f"{expr.func}() dropped: presentational only")
            return

        if expr.func == "strategy.entry":
            self._emit_entry(expr, pad)
            return

        if expr.func in ("strategy.close", "strategy.close_all"):
            self.next_lines.append(f"{pad}self.close()")
            return

        if expr.func == "strategy.exit":
            attached = {key for key, _ in expr.kwargs} & {
                "stop",
                "limit",
                "loss",
                "profit",
                "trail_price",
                "trail_points",
                "trail_offset",
            }
            if attached:
                self._reject(
                    "strategy.exit with "
                    + ", ".join(sorted(attached))
                    + ": bracket orders need an explicit Backtrader equivalent"
                )
                return
            self.next_lines.append(f"{pad}self.close()")
            return

        self._reject(f"call to {expr.func}() is not supported")

    def _emit_entry(self, call, pad):
        direction = None
        for arg in call.args:
            if isinstance(arg, Name) and arg.id in ("strategy.long", "strategy.short"):
                direction = arg.id
        for key, value in call.kwargs:
            if key == "direction" and isinstance(value, Name):
                direction = value.id
        if direction is None:
            self._reject("strategy.entry: could not determine long or short")
            return

        size = None
        for key, value in call.kwargs:
            if key in ("qty", "size"):
                size = self._value_expr(value)
        arguments = f"size={size}" if size else ""
        action = "buy" if direction == "strategy.long" else "sell"
        self.next_lines.append(f"{pad}self.{action}({arguments})")

    # --- assembly ------------------------------------------------------------

    def generate(self):
        if self.declaration is None:
            self._reject(
                "no strategy() or indicator() declaration found; "
                "this does not look like a complete script"
            )
        elif self.declaration[0] == "indicator":
            self._ignore(
                "script declares indicator(), not strategy(); "
                "the generated class computes its lines but places no orders"
            )

        for statement in self.program.body:
            self._emit_statement(statement, indent=0)

        return self._render()

    def _render(self):
        out = ["import backtrader as bt", "", ""]
        out.append(f"class {self.class_name}(bt.Strategy):")

        title = self.declaration[1] if self.declaration else ""
        out.append('    """Converted from PineScript by pwb_toolbox.converting.')
        if title:
            out.append("")
            out.append(f"    Original title: {title}")
        if self.unsupported:
            out.append("")
            out.append("    Not translated -- these still need writing by hand:")
            for item in self.unsupported:
                out.append(f"      - {item}")
        if self.ignored:
            out.append("")
            out.append("    Dropped as presentational:")
            for item in self.ignored:
                out.append(f"      - {item}")
        out.append('    """')
        out.append("")

        if self.params:
            out.append("    params = (")
            for name, default in self.params:
                out.append(f"        ({_safe(name)!r}, {default!r}),")
            out.append("    )")
            out.append("")

        out.append("    def __init__(self):")
        if self.init_lines:
            out.extend(f"        {line}" for line in self.init_lines)
        else:
            out.append("        pass")
        out.append("")

        out.append("    def next(self):")
        if self.next_lines:
            out.extend(f"        {line}" for line in self.next_lines)
        else:
            out.append("        pass")

        return "\n".join(out) + "\n"


def _unparsable(message: str, class_name: str | None) -> ConversionResult:
    """Build the result for source that could not be parsed at all.

    Still emits a class, so callers writing one file per script get a file
    that says what went wrong rather than a traceback. It inherits from
    ``bt.Strategy`` and does nothing, and ``ok`` is False.
    """
    name = class_name or "UnconvertedStrategy"
    code = (
        "import backtrader as bt\n"
        "\n"
        "\n"
        f"class {name}(bt.Strategy):\n"
        '    """PineScript that pwb_toolbox.converting could not parse.\n'
        "\n"
        f"    {message}\n"
        "\n"
        "    This class is a placeholder -- it trades nothing.\n"
        '    """\n'
        "\n"
        "    def next(self):\n"
        "        pass\n"
    )
    return ConversionResult(
        code=code,
        class_name=name,
        unsupported=[f"could not parse: {message}"],
    )


def convert(source: str, class_name: str | None = None) -> ConversionResult:
    """Convert PineScript source into a Backtrader strategy.

    The result always carries generated code; check ``result.ok`` (or read
    ``result.unsupported``) before trusting it to be a faithful port.

    Source this converter cannot even parse is reported the same way as source
    it can parse but not translate. Raising here would break the promise above
    and, worse, would kill a loop over a corpus on its first odd script -- the
    very thing this module exists to survive.
    """
    try:
        program = parse(source)
    except PineSyntaxError as error:
        return _unparsable(str(error), class_name)
    generator = _Generator(program, class_name=class_name)
    code = generator.generate()
    return ConversionResult(
        code=code,
        class_name=generator.class_name,
        params=generator.params,
        unsupported=generator.unsupported,
        ignored=generator.ignored,
    )
