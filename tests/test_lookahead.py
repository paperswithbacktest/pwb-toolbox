"""The look-ahead rules, ported from the papers repository with their tests.

The first part is ``tools/test_check_lookahead.py`` of the papers repository
(anchored calendar offsets: what pandas does, and what the rule must refuse),
unchanged but for the import. The second covers the other rules of the module
and how the harness finds the code it analyses.

`today - pd.offsets.MonthBegin(1)` reads as "the start of last month", and is that only
when `today` is itself a 1st. On any other day it rolls back to the first of the CURRENT
month. A strategy that rebalances on the first session of the month gets the month that
just ended when the 1st is a weekday, and the month that has just started -- the future --
when the 1st falls on a weekend and the first session is the 2nd or the 3rd.
"""

from __future__ import annotations

import os
import runpy
import sys
import tempfile
import textwrap

import pandas as pd

from pwb_toolbox.backtesting import lookahead
from pwb_toolbox.backtesting.lookahead import check_anchored_calendar_offsets

# A first session on the 1st, two first sessions after a weekend, and a 2 January.
MONDAY_THE_1ST = pd.Timestamp("2019-07-01")
MONDAY_THE_3RD = pd.Timestamp("2019-06-03")   # 1 June 2019 was a Saturday
THURSDAY_THE_2ND = pd.Timestamp("2020-01-02")


def _month(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m")


def test_month_begin_gives_the_previous_month_only_on_a_1st():
    assert _month(MONDAY_THE_1ST - pd.offsets.MonthBegin(1)) == "2019-06"
    # The same expression on the first session of June reads June, not May.
    assert _month(MONDAY_THE_3RD - pd.offsets.MonthBegin(1)) == "2019-06"
    assert _month(THURSDAY_THE_2ND - pd.offsets.MonthBegin(1)) == "2020-01"


def test_month_begin_then_minus_a_day_is_a_month_stale_on_a_1st():
    prev_end = lambda d: d - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)  # noqa: E731
    assert prev_end(MONDAY_THE_1ST) == pd.Timestamp("2019-05-31")
    assert prev_end(MONDAY_THE_3RD) == pd.Timestamp("2019-05-31")
    assert prev_end(THURSDAY_THE_2ND) == pd.Timestamp("2019-12-31")


def test_month_begin_zero_rolls_forward_off_the_1st():
    assert MONDAY_THE_1ST + pd.offsets.MonthBegin(0) == pd.Timestamp("2019-07-01")
    assert MONDAY_THE_3RD + pd.offsets.MonthBegin(0) == pd.Timestamp("2019-07-01")
    assert MONDAY_THE_3RD - pd.offsets.MonthBegin(0) == pd.Timestamp("2019-07-01")


def test_period_forms_give_the_month_just_ended_on_every_day():
    for day, ended in ((MONDAY_THE_1ST, "2019-06"), (MONDAY_THE_3RD, "2019-05"),
                       (THURSDAY_THE_2ND, "2019-12")):
        assert (day.to_period("M") - 1).strftime("%Y-%m") == ended
        assert _month(day.replace(day=1) - pd.Timedelta(days=1)) == ended


def test_week_anchor_skips_a_week_on_its_own_weekday():
    friday, wednesday = pd.Timestamp("2019-06-28"), pd.Timestamp("2019-06-26")
    assert friday + pd.offsets.Week(weekday=4) == pd.Timestamp("2019-07-05")
    assert wednesday + pd.offsets.Week(weekday=4) == pd.Timestamp("2019-06-28")
    assert pd.offsets.Week(weekday=4).rollback(friday) == friday
    assert pd.offsets.Week(weekday=4).rollback(wednesday) == pd.Timestamp("2019-06-21")


def _types(code: str) -> list[str]:
    return [issue["type"] for issue in check_anchored_calendar_offsets(code)]


ERROR = "lookahead_calendar_offset"
WARNING = "warning_calendar_offset"


def test_subtracting_a_begin_offset_is_an_error():
    for line in (
        'formed = (today - pd.offsets.MonthBegin(1)).strftime("%Y-%m")',
        "prev = today - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)",
        "prev = today - pd.offsets.MonthBegin()",
        "prev = today - MonthBegin(n=1)",
        "prev = today - _pd.offsets.BMonthBegin(1)",
        "prev = today - pd.tseries.offsets.QuarterBegin(1, startingMonth=1)",
        "prev = today - pd.offsets.YearBegin(k)",
        "prev = today + pd.offsets.MonthBegin(-1)",
        "start = (ts + pd.offsets.MonthBegin(0)).normalize()",
        "start = ts - pd.offsets.MonthBegin(0)",
    ):
        assert _types(line) == [ERROR], line


def test_forms_without_ambiguity_pass():
    for line in (
        'formed = (today.to_period("M") - 1).strftime("%Y-%m")',
        "prev_end = today.replace(day=1) - pd.Timedelta(days=1)",
        "prev = first_of_month - pd.DateOffset(months=1)",
        "nxt = d + pd.offsets.MonthBegin(1)",
        "nxt = d + pd.offsets.MonthBegin()",
        "prev_end = d - pd.offsets.MonthEnd(1)",
        "end = d + pd.offsets.MonthEnd(0)",
        "end = d - pd.offsets.MonthEnd(skip)",
        "start = pd.offsets.BMonthBegin(0).rollback(ts)",
        "fri = pd.offsets.Week(weekday=4).rollback(d)",
        "x = d - pd.offsets.BDay(1)",
        "# prev = today - pd.offsets.MonthBegin(1)",
        "prev = today  # not today - pd.offsets.MonthBegin(1)",
    ):
        assert _types(line) == [], line


def test_offsets_correct_only_on_an_anchor_are_warnings():
    for line in (
        "nxt = month_end + pd.offsets.MonthEnd(1)",
        "nxt = me + pd.offsets.BMonthEnd()",
        "q = q.index + pd.tseries.offsets.QuarterEnd(1)",
        "end = ts + pd.offsets.MonthEnd(hold)",
        "key = start + pd.offsets.MonthBegin(j)",
        'eff = weekly["week_end"] + _pd.offsets.Week(weekday=0)',
    ):
        assert _types(line) == [WARNING], line


def test_the_two_reported_defects_are_caught_as_written_on_main():
    information_factor = (
        '        formed = (today - pd.offsets.MonthBegin(1)).strftime("%Y-%m")'
        "  # the month just ended\n"
    )
    accounting = "        prev_month_end = today - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)\n"
    assert _types(information_factor) == [ERROR]
    assert _types(accounting) == [ERROR]
    assert check_anchored_calendar_offsets(information_factor)[0]["line"] == 1


# --------------------------------------------------------------------------- #
# The other rules
# --------------------------------------------------------------------------- #


def _kinds(code: str) -> list[str]:
    return [issue["type"] for issue in lookahead.analyse(code)["issues"]]


def test_a_positive_index_on_a_feed_is_an_error():
    for line in (
        "tomorrow = self.data.close[1]",
        "x = self.datas[0].open[2]",
        "hi = data0.high[1]",
        "d = self.data.datetime[1]",
    ):
        assert _kinds(line) == ["lookahead_positive_index"], line


def test_current_and_past_bars_are_fine():
    for line in (
        "today = self.data.close[0]",
        "yesterday = self.datas[0].close[-1]",
        "# tomorrow = self.data.close[1]",
        "x = prices[1]",
    ):
        assert _kinds(line) == [], line


def test_quarterly_fundamentals_need_a_reporting_lag():
    unlagged = textwrap.dedent(
        """
        bs = pwb_ds.load_dataset("Stocks-Quarterly-BalanceSheet")
        merged = pd.merge_asof(prices, bs, on="date")
        """
    )
    lagged = unlagged.replace(
        "merged =", 'bs["date"] = bs["date"] + pd.DateOffset(months=3)\nmerged ='
    )
    assert _kinds(unlagged) == ["lookahead_unlagged_fundamentals"]
    assert _kinds(lagged) == []


def test_a_forward_shift_is_a_warning():
    assert _kinds('df["label"] = df["ret"].shift(-1)') == ["warning_forward_shift"]
    assert _kinds('df["lag"] = df["ret"].shift(1)') == []


def test_datasets_are_checked_only_against_a_list():
    code = 'x = pwb_ds.load_dataset("Stocks-Daily-Price")'
    assert lookahead.analyse(code)["issues"] == []
    report = lookahead.analyse(code, ["Indices-Daily-Price"])
    assert [i["type"] for i in report["issues"]] == ["unauthorized_dataset"]


def test_the_report_counts_errors_and_warnings():
    code = "a = self.data.close[1]\nb = s.shift(-2)\n"
    report = lookahead.analyse(code)
    assert report["errors_count"] == 1
    assert report["warnings_count"] == 1


# --------------------------------------------------------------------------- #
# Finding the code
# --------------------------------------------------------------------------- #

STRATEGY = textwrap.dedent(
    """
    class Mine:
        def next(self):
            return 1

    found = probe()
    """
)


def _probe():
    return lookahead.strategy_source(None, None, sys._getframe(1))


def test_the_string_given_to_exec_is_recovered():
    code = STRATEGY  # what the site and the catalogue's server do: exec(code, namespace)
    namespace = {"__name__": "__main__", "probe": _probe}
    exec(code, namespace)
    assert namespace["found"] == [("exec", code)]


def test_a_string_that_only_looks_alike_is_not_taken():
    code = STRATEGY
    decoy = STRATEGY.replace("return 1", "return 2")  # noqa: F841 -- on the stack
    namespace = {"__name__": "__main__", "probe": _probe}
    exec(code, namespace)
    assert namespace["found"] == [("exec", code)]


def test_a_script_file_is_read():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "strategy.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(STRATEGY)
        result = runpy.run_path(path, init_globals={"probe": _probe})
    assert result["found"] == [(path, STRATEGY)]


def test_a_class_from_another_file_is_read_too():
    other = "class Imported:\n    def next(self):\n        return self.data.close[1]\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "other.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(other)
        cls = runpy.run_path(path)["Imported"]
        found = lookahead.strategy_source(cls, None, sys._getframe(0))
    # The caller is a test function, not a script: only the class's file is read.
    assert found == [(path, other)]


def test_nothing_found_is_an_empty_list():
    namespace = {"__name__": "__main__", "probe": _probe}
    exec(compile(STRATEGY, "<nowhere>", "exec"), namespace)  # no string left on the stack
    assert namespace["found"] == []
