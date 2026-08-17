"""Tests for `pwb_toolbox.converting`.

The important ones are at the bottom: generated strategies are compiled and run
through a real Backtrader `cerebro` on synthetic bars, so "it converted" is
never mistaken for "it works".
"""

import datetime
import random

import backtrader as bt
import pandas as pd
import pytest

from pwb_toolbox.converting import PineSyntaxError, convert, parse, tokenize
from pwb_toolbox.converting.nodes import (
    Assign,
    Binary,
    Call,
    If,
    Num,
    Ternary,
    Unsupported,
)

DUAL_MA = """//@version=5
strategy("Dual MA Cross", overlay=true)
fast = input.int(5, title="Fast length")
slow = input.int(20, title="Slow length")
maFast = ta.sma(close, fast)
maSlow = ta.sma(close, slow)
if ta.crossover(maFast, maSlow) and close > maSlow
    strategy.entry("long", strategy.long)
if ta.crossunder(maFast, maSlow)
    strategy.close("long")
plot(maFast)
"""

RSI_STRATEGY = """//@version=5
strategy("RSI Reversion")
length = input.int(14)
oversold = input.int(30)
overbought = input.int(70)
r = ta.rsi(close, length)
if r < oversold
    strategy.entry("long", strategy.long)
if r > overbought
    strategy.close("long")
"""


# --- lexer -------------------------------------------------------------------


def _kinds(source):
    return [t.kind for t in tokenize(source)]


def test_tokenize_emits_indent_and_dedent():
    kinds = _kinds("if close > open\n    strategy.close()\n")
    assert "INDENT" in kinds and "DEDENT" in kinds


def test_tokenize_lexes_dotted_names_as_single_token():
    tokens = [t for t in tokenize("ta.sma(close, 10)\n") if t.kind == "NAME"]
    assert [t.value for t in tokens] == ["ta.sma", "close"]


def test_tokenize_ignores_comment_and_blank_lines():
    assert _kinds("// just a comment\n\n") == ["EOF"]


def test_tokenize_keeps_double_slash_inside_string():
    tokens = [t for t in tokenize('x = "http://a.b"\n') if t.kind == "STRING"]
    assert tokens[0].value == "http://a.b"


def test_tokenize_ignores_newlines_inside_parentheses():
    kinds = _kinds("x = ta.sma(\n    close,\n    10\n)\n")
    assert kinds.count("NEWLINE") == 1
    assert "INDENT" not in kinds


def test_tokenize_rejects_unterminated_string():
    with pytest.raises(PineSyntaxError):
        tokenize('x = "oops\n')


# --- parser ------------------------------------------------------------------


def test_parse_reads_version_and_declaration():
    program = parse(DUAL_MA)
    assert program.version == 5
    assert program.declaration == ("strategy", "Dual MA Cross")


def test_parse_normalises_legacy_study_declaration():
    program = parse('//@version=4\nstudy("Legacy")\n')
    assert program.declaration == ("indicator", "Legacy")


def test_parse_builds_if_else_with_bodies():
    program = parse(
        "if close > open\n    strategy.close()\nelse\n    strategy.close()\n"
    )
    node = program.body[0]
    assert isinstance(node, If)
    assert len(node.body) == 1 and len(node.orelse) == 1


def test_parse_handles_else_if_chain():
    program = parse(
        "if close > open\n    strategy.close()\n"
        "else if close < open\n    strategy.close()\n"
    )
    assert isinstance(program.body[0].orelse[0], If)


def test_parse_respects_arithmetic_precedence():
    program = parse("x = 1 + 2 * 3\n")
    value = program.body[0].value
    assert value.op == "+" and value.right.op == "*"


def test_parse_comparison_binds_looser_than_arithmetic():
    program = parse("x = close - 1 > open\n")
    value = program.body[0].value
    assert value.op == ">" and value.left.op == "-"


def test_parse_ternary():
    program = parse("x = close > open ? 1 : 2\n")
    assert isinstance(program.body[0].value, Ternary)


def test_parse_history_index():
    program = parse("x = close[1]\n")
    assert program.body[0].value.offset == Num(1.0)


def test_parse_keyword_arguments():
    program = parse('x = input.int(10, title="Len")\n')
    call = program.body[0].value
    assert call.args == (Num(10.0),)
    assert call.kwargs[0][0] == "title"


def test_parse_records_var_qualifier():
    program = parse("var count = 0\n")
    assert program.body[0].qualifier == "var"


def test_parse_skips_for_loop_as_unsupported():
    program = parse("for i = 0 to 10\n    x = i\ny = close\n")
    assert isinstance(program.body[0], Unsupported)
    assert program.body[0].kind == "for"
    # Parsing must resume cleanly after the skipped block.
    assert isinstance(program.body[1], Assign)


def test_parse_rejects_unknown_character():
    with pytest.raises(PineSyntaxError):
        parse("x = 1 @ 2\n")


# --- conversion: structure ---------------------------------------------------


def test_convert_collects_inputs_as_params():
    result = convert(DUAL_MA)
    assert result.params == [("fast", 5), ("slow", 20)]
    assert "('fast', 5)" in result.code


def test_convert_derives_class_name_from_title():
    assert convert(DUAL_MA).class_name == "DualMACross"


def test_convert_honours_explicit_class_name():
    assert convert(DUAL_MA, class_name="MyStrat").class_name == "MyStrat"


def test_convert_hoists_indicators_into_init():
    code = convert(DUAL_MA).code
    init = code.split("def __init__")[1].split("def next")[0]
    assert "bt.indicators.SMA(self.data.close, period=self.p.fast)" in init
    assert "bt.indicators.SMA" not in code.split("def next")[1]


def test_convert_shares_one_crossover_between_crossover_and_crossunder():
    """Backtrader recomputes every indicator each bar; duplicates are waste."""
    init = convert(DUAL_MA).code.split("def __init__")[1].split("def next")[0]
    assert init.count("bt.indicators.CrossOver") == 1


def test_convert_maps_cross_helpers_to_their_direction():
    next_body = convert(DUAL_MA).code.split("def next")[1]
    assert "> 0" in next_body and "< 0" in next_body


def test_convert_maps_entry_and_close_to_orders():
    next_body = convert(DUAL_MA).code.split("def next")[1]
    assert "self.buy()" in next_body
    assert "self.close()" in next_body


def test_convert_maps_short_entry_to_sell():
    source = '//@version=5\nstrategy("S")\nif close > open\n    strategy.entry("s", strategy.short)\n'
    assert "self.sell()" in convert(source).code


def test_convert_passes_entry_quantity_as_size():
    source = (
        '//@version=5\nstrategy("S")\nif close > open\n'
        '    strategy.entry("l", strategy.long, qty=5)\n'
    )
    assert "self.buy(size=5)" in convert(source).code


def test_convert_reports_plot_as_ignored_not_unsupported():
    result = convert(DUAL_MA)
    assert result.ok
    assert any("plot()" in item for item in result.ignored)
    assert result.unsupported == []


def test_convert_translates_history_access():
    source = '//@version=5\nstrategy("S")\nif close > close[1]\n    strategy.close()\n'
    assert "self.data.close[-1]" in convert(source).code


def test_convert_translates_derived_series():
    source = '//@version=5\nstrategy("S")\nif hl2 > close\n    strategy.close()\n'
    code = convert(source).code
    assert "self.data.high[0] + self.data.low[0]" in code


def test_convert_translates_ternary():
    source = '//@version=5\nstrategy("S")\nx = close > open ? 1 : 2\nif x > 1\n    strategy.close()\n'
    assert "if" in convert(source).code and "else" in convert(source).code


def test_convert_atr_takes_no_source_argument():
    source = (
        '//@version=5\nstrategy("S")\na = ta.atr(14)\nif a > 1\n    strategy.close()\n'
    )
    result = convert(source)
    assert result.ok, result.unsupported
    assert "bt.indicators.ATR(self.data, period=14)" in result.code


def test_convert_highest_defaults_to_high_series():
    source = '//@version=5\nstrategy("S")\nh = ta.highest(20)\nif close > h\n    strategy.close()\n'
    result = convert(source)
    assert result.ok, result.unsupported
    assert "bt.indicators.Highest(self.data.high, period=20)" in result.code


# --- conversion: refusals ----------------------------------------------------


def _unsupported(source):
    return convert(source).unsupported


@pytest.mark.parametrize(
    "snippet, marker",
    [
        ("s = request.security(syminfo.tickerid, '1D', close)\n", "request.security"),
        ("var count = 0\n", "var count"),
        ("for i = 0 to 10\n    x = close\n", "for"),
        ("[m, s, h] = ta.macd(close, 12, 26, 9)\n", "tuple destructuring"),
        ("a = array.new_float(0)\n", "array.new_float"),
    ],
)
def test_convert_reports_untranslatable_constructs(snippet, marker):
    result = convert('//@version=5\nstrategy("S")\n' + snippet)
    assert not result.ok
    assert any(marker in item for item in result.unsupported)


def test_convert_reports_strategy_exit_with_a_stop():
    source = (
        '//@version=5\nstrategy("S")\nif close > open\n'
        '    strategy.exit("x", stop=100)\n'
    )
    result = convert(source)
    assert not result.ok
    assert any("bracket orders" in item for item in result.unsupported)


def test_convert_allows_plain_strategy_exit():
    source = '//@version=5\nstrategy("S")\nif close > open\n    strategy.exit("x")\n'
    result = convert(source)
    assert result.ok, result.unsupported
    assert "self.close()" in result.code


def test_convert_reports_unknown_identifier():
    source = '//@version=5\nstrategy("S")\nif mystery > 1\n    strategy.close()\n'
    assert any("mystery" in item for item in _unsupported(source))


def test_convert_reports_missing_declaration():
    result = convert("x = ta.sma(close, 10)\n")
    assert not result.ok
    assert any("declaration" in item for item in result.unsupported)


def test_convert_notes_indicator_scripts_place_no_orders():
    result = convert('//@version=5\nindicator("Just Lines")\nx = ta.sma(close, 10)\n')
    assert result.ok
    assert any("places no orders" in item for item in result.ignored)


def test_unsupported_items_appear_in_generated_docstring():
    code = convert('//@version=5\nstrategy("S")\nvar c = 0\n').code
    assert "Not translated" in code and "var c" in code


def test_reserved_names_are_renamed_to_avoid_clobbering_strategy_attrs():
    source = '//@version=5\nstrategy("S")\nposition = input.int(3)\nif close > position\n    strategy.close()\n'
    result = convert(source)
    assert result.ok, result.unsupported
    assert "'pine_position'" in result.code


# --- end to end: the generated code must actually run ------------------------


def _price_frame(bars=300, seed=7):
    rng = random.Random(seed)
    price = 100.0
    start = datetime.datetime(2022, 1, 1)
    rows = []
    for i in range(bars):
        price *= 1 + rng.gauss(0, 0.02)
        rows.append(
            {
                "datetime": start + datetime.timedelta(days=i),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows).set_index("datetime")


def _run(source, **params):
    result = convert(source)
    assert result.ok, f"conversion reported: {result.unsupported}"

    namespace = {}
    exec(compile(result.code, "<converted>", "exec"), namespace)

    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=_price_frame()))
    cerebro.addstrategy(namespace[result.class_name], **params)
    cerebro.broker.setcash(10_000.0)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    strategy = cerebro.run()[0]
    closed = strategy.analyzers.trades.get_analysis().get("total", {}).get("total", 0)
    return cerebro.broker.getvalue(), closed


def test_generated_strategy_compiles_and_runs():
    value, _ = _run(DUAL_MA)
    assert value > 0


def test_generated_strategy_actually_places_orders():
    """A converted strategy that never trades has not really been converted."""
    _, closed = _run(DUAL_MA)
    assert closed > 0


def test_generated_rsi_strategy_runs_and_trades():
    _, closed = _run(RSI_STRATEGY)
    assert closed > 0


def test_generated_params_are_overridable_from_cerebro():
    """Pine inputs must land as real Backtrader params, not baked-in constants."""
    baseline, _ = _run(DUAL_MA)
    tuned, _ = _run(DUAL_MA, fast=3, slow=40)
    assert baseline != tuned


def test_generated_history_access_runs():
    source = (
        '//@version=5\nstrategy("Momentum")\n'
        'if close > close[5]\n    strategy.entry("l", strategy.long)\n'
        "if close < close[5]\n    strategy.close()\n"
    )
    _, closed = _run(source)
    assert closed > 0
