# Converting PineScript to Backtrader

`pwb_toolbox.converting` turns a PineScript strategy into a Backtrader one.

```python
from pwb_toolbox.converting import convert

result = convert(pine_source)
if result.ok:
    print(result.code)
else:
    print("still needs work:", result.unsupported)
```

Paired with the scraping module, that is a pipeline from a published script to
a runnable strategy:

```python
from pwb_toolbox.scraping import ScriptStore
from pwb_toolbox.converting import convert

for record in ScriptStore("script-corpus").records():
    if record.language == "pinescript":
        result = convert(record.code, class_name=None)
        print(record.title, "->", "ok" if result.ok else result.unsupported)
```

## Read this first

This is **not** a complete transpiler, and one cannot be written in a weekend.
Pine is a real language with multi-timeframe requests, persistent variables,
arrays, matrices, maps, user-defined types and libraries. Its execution model —
every expression is a series evaluated on every bar — does not line up with
Backtrader's, where an indicator is a line object built once and indexed per
bar.

What this does cover is the shape most published strategies actually take: a
declaration, some inputs, a handful of `ta.*` indicators, conditions, and entry
and exit calls. Everything else is **reported, not guessed**.

A result with a non-empty `unsupported` list is a starting point plus a to-do
list. It is not a working port, and `result.ok` tells you which you have.

## The core translation

Pine lets you write `ta.sma(close, 20)` anywhere because it is a series.
Backtrader needs that indicator constructed once in `__init__` and then indexed
in `next`. So the converter **hoists**:

```pinescript
maFast = ta.sma(close, fast)
if ta.crossover(maFast, maSlow)
    strategy.entry("long", strategy.long)
```

becomes

```python
def __init__(self):
    self._sma_1 = bt.indicators.SMA(self.data.close, period=self.p.fast)
    self._sma_2 = bt.indicators.SMA(self.data.close, period=self.p.slow)
    self._cross_3 = bt.indicators.CrossOver(self._sma_1, self._sma_2)

def next(self):
    if self._cross_3[0] > 0:
        self.buy()
```

Identical constructions are shared. `ta.crossover(a, b)` and
`ta.crossunder(a, b)` on the same pair produce **one** `CrossOver`, compared in
two directions — Backtrader recomputes every indicator on every bar, so a
duplicate is pure waste.

## What is translated

| Pine | Backtrader |
| --- | --- |
| `strategy("T")` / `indicator("T")` | class name and docstring |
| `input.int/float/bool/string(...)` | entries in `params` |
| `float x = ...`, `series int n = ...` | the type annotation is dropped |
| `ta.sma/ema/wma/rma/rsi/stdev/highest/lowest/atr/tr` | `bt.indicators.*` |
| `ta.crossover/crossunder/cross` | `CrossOver` plus a direction test |
| `ta.change(src, n)` | `src[0] - src[-n]` |
| `close`, `open`, `high`, `low`, `volume` | `self.data.<line>[0]` |
| `hl2`, `hlc3`, `ohlc4` | the arithmetic spelled out |
| `close[3]` | `self.data.close[-3]` |
| `and` / `or` / `not`, comparisons, arithmetic | the Python equivalents |
| `cond ? a : b` | `a if cond else b` |
| `if` / `else if` / `else` | the same, inside `next()` |
| `strategy.entry(..., strategy.long/short, qty=)` | `self.buy(size=)` / `self.sell(size=)` |
| `strategy.close`, `strategy.close_all`, plain `strategy.exit` | `self.close()` |
| `strategy.position_size` | `self.position.size` |
| `bar_index` | `len(self)` |
| `var x = <literal>` | an attribute set once in `__init__` |
| `x := value` | assignment, writing through to the attribute for a `var` |
| `na(x)` | the NaN test `x != x` |
| `math.abs/max/min/round`, `nz` | the Python equivalents |

Pine inputs become real Backtrader params, so they stay tunable:

```python
cerebro.addstrategy(DualMACross, fast=3, slow=40)
```

An input does not have to be the whole right-hand side. The percentage idiom
works too, and the param is named from the input's title when there is no
variable to take the name from:

```pinescript
stop = input.float(5.0, "Stop Percent") / 100
```

```python
params = (('stop_percent', 5),)
...
stop = (self.p.stop_percent / 100)
```

Where a title-derived name collides with a variable, the computed local wins
every later reference — that is what the Pine source means by the name.

## What is refused

Reported in `result.unsupported`, never approximated:

- `request.security` — multi-timeframe needs a second data feed and a resampling decision
- `varip` — updates on every tick, and a bar-close run has no ticks
- `var x = <expression>` — only a literal initial value works; see below
- arrays, matrices, maps, user-defined functions and types
- `for` / `while` loops
- tuple destructuring, e.g. `[macd, signal, hist] = ta.macd(...)`
- `strategy.exit` carrying `stop`, `limit`, `trail_*` — bracket orders differ enough that a guess would silently change behavior
- any identifier or call the converter does not know

Reported separately in `result.ignored`, because dropping them changes nothing
about how the strategy trades: `plot`, `plotshape`, `bgcolor`, `hline`, `fill`,
`alertcondition`, `label.new`, `line.new`, and friends — along with the drawing
constants they consume, such as `color.green` and `shape.triangleup`. A colour
cannot change a trade, so refusing one would fail a conversion over nothing.

Both lists are also written into the generated class's docstring, so a
converted file explains its own gaps without needing the original result object.

## State that survives the bar

`var` is how a strategy remembers something between bars — the price it got
filled at, a stop level, a counter. Pine initialises a `var` once and keeps it;
a Backtrader instance attribute already behaves that way, so that is what it
becomes.

```pinescript
var float entryPrice = na
var int trades = 0
if na(entryPrice) and close > ma
    strategy.entry("long", strategy.long)
    entryPrice := close
    trades := trades + 1
```

```python
def __init__(self):
    self.entryPrice = float('nan')
    self.trades = 0

def next(self):
    if (self.entryPrice != self.entryPrice) and (self.data.close[0] > self._sma_1[0]):
        self.buy()
        self.entryPrice = self.data.close[0]
        self.trades = (self.trades + 1)
```

`na(x)` lowers to the NaN test `x != x`, which is what pairs with
`var float x = na` — the usual way a script spells "no position yet".

A `var` named after something a `bt.Strategy` already owns is renamed, exactly
as params are: `var position = 0` becomes `self.pine_position`, so it cannot
quietly overwrite Backtrader's own `position`.

Two limits, both reported rather than guessed at:

- **The initial value must be a literal.** `var float x = close` means the
  *first bar's* close, and `__init__` runs before there is a first bar. Numbers,
  strings, booleans and `na` all work; anything reading a series does not.
- **A `var` has no history.** `entryPrice[1]` needs a real line object. One
  attribute holds one value.

The test suite runs a converted `var` strategy through a real `cerebro` and
checks the Pine counter matches the broker's own trade count. Compiling proves
nothing here — a local assigned in `next()` compiles too, and would silently
count to one and stay there.

## Source it cannot even parse

`convert` does not raise on malformed or unrecognised syntax. It returns a
result like any other, with the parse error in `unsupported` and a placeholder
strategy as `code`:

```python
result = convert(broken_source)
result.ok            # False
result.unsupported   # ["could not parse: expected 'NEWLINE' but found 'x' on line 32"]
```

This matters for the corpus loop at the top of this page. Raising would kill
that loop on its first odd script and tell you nothing about the rest — which is
exactly what the module exists to avoid.

## A known simplification

Only a bare `ta.*` call on the right-hand side of an assignment is hoisted into
`__init__`. Compound expressions such as `spread = maFast - maSlow` are computed
in `next()` from indexed values instead of becoming a Backtrader line.

That is correct for evaluating conditions, which is what strategies do with
them, and it avoids a class of bugs where a partially-lowered expression looks
like a line object but is not one. The cost: `spread[1]` — history of a computed
value — is refused rather than supported, because it would need a real line
object to be meaningful.

## Verification

Unlike the scraping collectors, this module can be checked end to end locally,
and is. The test suite compiles generated strategies and runs them through a
real `cerebro` on synthetic bars, asserting that they execute, place orders, and
respond to parameter overrides. "It converted" is never taken to mean "it works".
