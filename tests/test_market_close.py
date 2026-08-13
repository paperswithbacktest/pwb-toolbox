"""Tests for the daily market-close script generator.

Everything here runs offline: the data reduction is exercised against frames
built in-process and the renderer against ``demo_facts``, so nothing needs
``PWB_API_KEY``, a Hugging Face login, or a live session.
"""

from datetime import date

import pandas as pd
import pytest

from tools.market_close import market, script, spoken
from tools.market_close.cli import main, warn_on_digits
from tools.market_close.market import MarketFacts, Quote
from tools.market_close.script import ScriptOptions

# --------------------------------------------------------------------------
# spoken numbers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "zero"),
        (1, "one"),
        (19, "nineteen"),
        (20, "twenty"),
        (21, "twenty-one"),
        (100, "a hundred"),
        (109, "a hundred and nine"),
        (140, "a hundred and forty"),
        (319, "three hundred and nineteen"),
        (1_140, "one thousand one hundred and forty"),
        (5_432, "five thousand four hundred and thirty-two"),
        (68_400, "sixty-eight thousand four hundred"),
        (2_026, "two thousand and twenty-six"),
        (-7, "negative seven"),
    ],
)
def test_int_to_words(value, expected):
    assert spoken.int_to_words(value) == expected


def test_hundreds_only_lead_with_the_article():
    """ "A hundred and forty" opens a number; mid-number it is "one hundred"."""
    assert spoken.int_to_words(140) == "a hundred and forty"
    assert "one hundred and forty" in spoken.int_to_words(1_140)


@pytest.mark.parametrize(
    "day,expected",
    [
        (1, "first"),
        (2, "second"),
        (3, "third"),
        (4, "fourth"),
        (11, "eleventh"),
        (12, "twelfth"),
        (13, "thirteenth"),
        (20, "twentieth"),
        (21, "twenty-first"),
        (30, "thirtieth"),
    ],
)
def test_ordinal_to_words(day, expected):
    assert spoken.ordinal_to_words(day) == expected


@pytest.mark.parametrize(
    "pct,expected",
    [
        (0.6, "six tenths of a percent"),
        (-0.6, "six tenths of a percent"),  # sign belongs to the verb
        (0.9, "nine tenths of a percent"),
        (0.1, "a tenth of a percent"),
        (0.25, "a quarter percent"),
        (0.26, "a quarter percent"),
        (0.5, "half a percent"),
        (0.75, "three quarters of a percent"),
        (0.28, "three tenths of a percent"),
        (1.0, "one percent"),
        (1.4, "one point four percent"),
        (2.5, "two and a half percent"),
        (14.0, "fourteen percent"),
        (0.001, "a fraction of a percent"),
    ],
)
def test_say_percent_uses_desk_idiom(pct, expected):
    assert spoken.say_percent(pct) == expected


@pytest.mark.parametrize(
    "rate,expected",
    [
        (4.09, "four-oh-nine"),
        (4.25, "four-twenty-five"),
        (4.10, "four-ten"),
        (4.00, "four percent"),
        (3.5, "three-fifty"),
    ],
)
def test_say_yield(rate, expected):
    assert spoken.say_yield(rate) == expected


def test_say_yield_rounds_into_the_next_whole_number():
    assert spoken.say_yield(4.996) == "five percent"


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, "one basis point"),
        (-1, "one basis point"),
        (3, "three basis points"),
        (25, "twenty-five basis points"),
    ],
)
def test_say_basis_points(value, expected):
    assert spoken.say_basis_points(value) == expected


@pytest.mark.parametrize(
    "amount,expected",
    [
        (71.40, "seventy-one dollars and forty cents"),
        (27.00, "twenty-seven dollars"),
        (128.4, "a hundred and twenty-eight dollars and forty cents"),
        (68_400.0, "sixty-eight thousand four hundred dollars"),
    ],
)
def test_say_dollars(amount, expected):
    assert spoken.say_dollars(amount) == expected


def test_say_dollars_carries_rounded_cents_into_the_dollar():
    assert spoken.say_dollars(9.999) == "ten dollars"


def test_say_points_and_ticker_and_date():
    assert spoken.say_points(140) == "a hundred and forty points"
    assert spoken.say_points(1) == "one point"
    assert spoken.say_ticker("NVDA") == "N V D A"
    assert spoken.say_date(date(2026, 8, 13)) == "Thursday, August thirteenth"


# --------------------------------------------------------------------------
# data reduction
# --------------------------------------------------------------------------


def prices(rows):
    """Build a long price frame from ``(date, symbol, close)`` triples."""
    return pd.DataFrame(rows, columns=["date", "symbol", "close"])


DAY_ONE = date(2026, 8, 12)
DAY_TWO = date(2026, 8, 13)


def test_latest_changes_pairs_the_last_two_observations():
    df = prices(
        [
            (DAY_ONE, "AAA", 100.0),
            (DAY_TWO, "AAA", 110.0),
            (DAY_ONE, "BBB", 50.0),
            (DAY_TWO, "BBB", 45.0),
        ]
    )
    changes = market.latest_changes(df).set_index("symbol")
    assert changes.loc["AAA", "close"] == 110.0
    assert changes.loc["AAA", "previous_close"] == 100.0
    assert changes.loc["BBB", "previous_close"] == 50.0


def test_latest_changes_drops_symbols_with_a_single_observation():
    """A session move needs two points; a half-known symbol is worse than none."""
    df = prices([(DAY_TWO, "NEW", 10.0), (DAY_ONE, "OLD", 5.0), (DAY_TWO, "OLD", 6.0)])
    assert set(market.latest_changes(df)["symbol"]) == {"OLD"}


def test_latest_changes_ignores_older_history():
    df = prices(
        [
            (date(2026, 1, 2), "AAA", 1.0),
            (DAY_ONE, "AAA", 100.0),
            (DAY_TWO, "AAA", 110.0),
        ]
    )
    row = market.latest_changes(df).iloc[0]
    assert row["previous_close"] == 100.0


def test_latest_changes_on_empty_frame():
    assert market.latest_changes(pd.DataFrame()).empty


def test_movers_picks_the_extremes():
    df = prices(
        [
            (DAY_ONE, "UP", 100.0),
            (DAY_TWO, "UP", 120.0),
            (DAY_ONE, "FLAT", 100.0),
            (DAY_TWO, "FLAT", 101.0),
            (DAY_ONE, "DOWN", 100.0),
            (DAY_TWO, "DOWN", 80.0),
        ]
    )
    gainer, loser = market.movers(df)
    assert gainer.symbol == "UP"
    assert loser.symbol == "DOWN"
    assert gainer.percent_change == pytest.approx(20.0)
    assert loser.percent_change == pytest.approx(-20.0)


def test_movers_skips_penny_names():
    """A forty-percent move off a two-dollar base is an artifact, not a story."""
    df = prices(
        [
            (DAY_ONE, "PENNY", 2.0),
            (DAY_TWO, "PENNY", 3.0),
            (DAY_ONE, "REAL", 100.0),
            (DAY_TWO, "REAL", 110.0),
        ]
    )
    gainer, _ = market.movers(df)
    assert gainer.symbol == "REAL"


def test_movers_on_empty_frame():
    assert market.movers(pd.DataFrame()) == (None, None)


def test_movers_names_known_companies_and_spells_the_rest():
    df = prices(
        [
            (DAY_ONE, "NVDA", 100.0),
            (DAY_TWO, "NVDA", 120.0),
            (DAY_ONE, "ZZZZ", 100.0),
            (DAY_TWO, "ZZZZ", 80.0),
        ]
    )
    gainer, loser = market.movers(df)
    assert gainer.name == "Nvidia"
    assert loser.name == "Z Z Z Z"


def test_movers_accepts_a_names_override():
    df = prices([(DAY_ONE, "ZZZZ", 100.0), (DAY_TWO, "ZZZZ", 120.0)])
    gainer, _ = market.movers(df, names={"ZZZZ": "Zed Industries"})
    assert gainer.name == "Zed Industries"


def test_breadth_counts_advancers_and_decliners():
    df = prices(
        [
            (DAY_ONE, "A", 10.0),
            (DAY_TWO, "A", 11.0),
            (DAY_ONE, "B", 10.0),
            (DAY_TWO, "B", 9.0),
            (DAY_ONE, "C", 10.0),
            (DAY_TWO, "C", 10.0),  # unchanged counts as neither
        ]
    )
    assert market.breadth(df) == (1, 1)


def test_session_date_takes_the_latest():
    df = prices([(DAY_ONE, "A", 1.0), (DAY_TWO, "A", 2.0)])
    assert market.session_date(df) == DAY_TWO
    assert market.session_date(pd.DataFrame()) is None


def test_quote_percent_change_survives_a_zero_previous_close():
    assert Quote("X", "X", 10.0, 0.0).percent_change == 0.0


@pytest.mark.parametrize(
    "changes,expected",
    [
        ([0.6, 0.9, 0.4], "up"),
        ([-0.6, -0.9], "down"),
        ([0.6, -0.9], "mixed"),
        ([0.01, -0.01], "mixed"),
    ],
)
def test_direction(changes, expected):
    facts = MarketFacts(
        session_date=DAY_TWO,
        indices=[
            Quote(f"I{i}", "idx", 100.0 + c, 100.0) for i, c in enumerate(changes)
        ],
    )
    assert facts.direction == expected


def test_narrow_breadth_needs_a_real_sample():
    assert MarketFacts(DAY_TWO, advancers=1, decliners=4).is_narrow is False
    assert MarketFacts(DAY_TWO, advancers=181, decliners=319).is_narrow is True
    assert MarketFacts(DAY_TWO, advancers=300, decliners=200).is_narrow is False


# --------------------------------------------------------------------------
# rotation
# --------------------------------------------------------------------------


def test_pick_is_stable_for_a_given_date():
    bank = ["a", "b", "c", "d"]
    assert script.pick(bank, DAY_TWO, "salt") == script.pick(bank, DAY_TWO, "salt")


def test_pick_varies_across_dates_and_salts():
    bank = [str(n) for n in range(40)]
    days = [date(2026, 8, day) for day in range(1, 15)]
    assert len({script.pick(bank, day, "cold-open") for day in days}) > 1
    assert script.pick(bank, DAY_TWO, "gainer") != script.pick(bank, DAY_TWO, "loser")


def test_pick_rejects_an_empty_bank():
    with pytest.raises(ValueError):
        script.pick([], DAY_TWO, "salt")


def test_a_working_week_does_not_repeat_the_cold_open():
    week = [date(2026, 8, day) for day in range(10, 15)]
    lines = {script.pick(script.COLD_OPEN["up"], day, "cold-open") for day in week}
    assert len(lines) >= 3


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def test_render_includes_every_segment():
    text = script.render(market.demo_facts())
    for header in (
        "[COLD OPEN]",
        "[THE TAPE]",
        "[MOVERS]",
        "[RATES]",
        "[COMMODITIES]",
        "[THE STRAIGHT BEAT]",
        "[KICKER]",
        "[SIGN-OFF]",
    ):
        assert header in text


def test_rendered_script_contains_no_digits():
    """The production invariant: ElevenLabs must never see a numeral.

    Every figure is spelled by ``spoken.py`` before it reaches the script, so
    a digit surviving to the output is a formatting path somebody forgot.
    """
    text = script.render(market.demo_facts())
    offenders = [line for line in text.splitlines() if any(c.isdigit() for c in line)]
    assert offenders == []


def test_no_digits_across_a_sweep_of_sessions():
    """Same invariant, over values that exercise each numeric branch."""
    for step, pct in enumerate([-12.5, -1.0, -0.25, 0.0, 0.1, 0.75, 3.33, 21.0]):
        for yield_rate in (0.5, 3.07, 4.0, 4.25, 11.9):
            facts = MarketFacts(
                session_date=date(2026, 8, 1 + step),
                indices=[
                    Quote("SPX", market.INDEX_NAMES["SPX"], 100.0 + pct, 100.0),
                    Quote("INDU", market.INDEX_NAMES["INDU"], 39_000.0 + pct, 39_000.0),
                ],
                gainer=Quote("NVDA", "Nvidia", 100.0 + abs(pct), 100.0),
                loser=Quote("PFE", "Pfizer", 100.0 - abs(pct), 100.0),
                advancers=181,
                decliners=319,
                rate=Quote("US10Y", "the ten-year", yield_rate, yield_rate + 0.03),
                crude=Quote("CL1", "crude", 71.4 + pct, 71.4),
                crypto=Quote("BTC", "Bitcoin", 68_400.0, 65_100.0),
            )
            text = script.render(facts)
            assert not any(c.isdigit() for c in text), text


def test_the_straight_beat_never_rotates():
    """The disclaimer is fixed on purpose — see the module docstring."""
    renders = [
        script.render(market.demo_facts(date(2026, 8, day))) for day in range(10, 15)
    ]
    for text in renders:
        assert script.STRAIGHT_BEAT in text
        assert "Nothing in this broadcast is advice." in text


def test_segments_without_data_are_dropped_not_faked():
    facts = MarketFacts(session_date=DAY_TWO)
    text = script.render(facts)
    assert "[THE TAPE]" not in text
    assert "[MOVERS]" not in text
    assert "[RATES]" not in text
    assert "[COMMODITIES]" not in text
    # The three that never depend on market data still stand.
    assert "[COLD OPEN]" in text
    assert "[THE STRAIGHT BEAT]" in text
    assert "[SIGN-OFF]" in text


def test_index_units_are_stated_once_then_dropped():
    """An anchor says "six tenths of a percent" then just "nine tenths"."""
    text = script.tape(market.demo_facts())
    assert "closed up six tenths of a percent" in text
    assert "The Nasdaq gained nine tenths." in text


def test_the_dow_is_quoted_in_points():
    assert "The Dow added a hundred and forty points" in script.tape(
        market.demo_facts()
    )


def test_tape_capitalizes_the_opening_index_name():
    assert script.tape(market.demo_facts()).count("The S and P five hundred") == 1


def test_flat_indices_are_described_not_quoted():
    facts = MarketFacts(
        session_date=DAY_TWO,
        indices=[Quote("SPX", market.INDEX_NAMES["SPX"], 100.001, 100.0)],
    )
    assert "finished essentially flat" in script.tape(facts)


def test_rate_joke_matches_the_size_of_the_move():
    """ "A move of approximately nothing" is wrong on twenty basis points."""
    quiet = MarketFacts(
        session_date=DAY_TWO, rate=Quote("US10Y", "the ten-year", 4.09, 4.12)
    )
    loud = MarketFacts(
        session_date=DAY_TWO, rate=Quote("US10Y", "the ten-year", 4.09, 4.34)
    )
    assert script.rates(quiet) is not None
    assert any(joke in script.rates(quiet) for joke in script.RATE_JOKES_SMALL)
    assert any(joke in script.rates(loud) for joke in script.RATE_JOKES_LARGE)


def test_rates_reads_to_the_level_but_at_it_when_unchanged():
    moved = MarketFacts(DAY_TWO, rate=Quote("US10Y", "the ten-year", 4.09, 4.12))
    still = MarketFacts(DAY_TWO, rate=Quote("US10Y", "the ten-year", 4.09, 4.0901))
    assert "to four-oh-nine" in script.rates(moved)
    assert "was effectively unchanged, at four-oh-nine" in script.rates(still)


def test_movers_segment_never_asserts_a_cause():
    """The generator has prices, not press releases. See the module docstring."""
    text = script.movers(market.demo_facts())
    for invented in ("after the company", "beat expectations", "following", "because"):
        assert invented not in text


def test_options_carry_through_to_the_script():
    text = script.render(
        market.demo_facts(),
        ScriptOptions(anchor="Robin Vale", show="the Closing Bell", kicker="A parrot."),
    )
    assert "I'm Robin Vale" in text
    assert "the Closing Bell" in text
    assert "A parrot." in text
    assert "Write the kicker by hand" not in text


def test_kicker_placeholder_appears_when_none_is_supplied():
    assert "Write the kicker by hand" in script.render(market.demo_facts())


def test_split_segments_round_trips_the_render():
    text = script.render(market.demo_facts())
    pairs = script.split_segments(text)
    names = [name for name, _ in pairs]
    assert names[0] == "cold-open"
    assert names[-1] == "sign-off"
    assert "the-straight-beat" in names
    assert all(body for _, body in pairs)
    assert not any(body.startswith("[COLD OPEN]") for _, body in pairs)


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------


def test_preview_carries_the_tape_and_movers_only():
    text = script.preview(market.demo_facts())
    assert "[THE TAPE]" in text
    assert "[MOVERS]" in text
    for dropped in ("[COLD OPEN]", "[RATES]", "[COMMODITIES]", "[KICKER]"):
        assert dropped not in text
    assert "[THE STRAIGHT BEAT]" not in text
    assert "[SIGN-OFF]" not in text


def test_preview_matches_the_full_render_word_for_word():
    """A preview that read differently from the broadcast would be useless."""
    facts = market.demo_facts()
    text = script.preview(facts)
    full = script.render(facts)
    for _, body in script.split_segments(text):
        assert body in full


def test_preview_keeps_the_no_digits_invariant():
    text = script.preview(market.demo_facts())
    assert not any(c.isdigit() for c in text)


def test_preview_is_empty_without_market_data():
    assert script.preview(MarketFacts(session_date=DAY_TWO)) == ""


def test_preview_survives_one_missing_segment():
    facts = MarketFacts(
        session_date=DAY_TWO,
        indices=[Quote("SPX", market.INDEX_NAMES["SPX"], 100.6, 100.0)],
    )
    text = script.preview(facts)
    assert "[THE TAPE]" in text
    assert "[MOVERS]" not in text


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def test_warn_on_digits_flags_a_hand_written_kicker():
    assert warn_on_digits("all spelled out") == []
    assert warn_on_digits("up 4.09 percent") == ["up 4.09 percent"]


def test_cli_demo_writes_a_script(tmp_path, capsys):
    out = tmp_path / "close.txt"
    assert main(["--demo", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "[COLD OPEN]" in text
    assert "Max Brennan" in text


def test_cli_demo_prints_to_stdout(capsys):
    assert main(["--demo"]) == 0
    assert "[THE STRAIGHT BEAT]" in capsys.readouterr().out


def test_cli_writes_numbered_segment_files(tmp_path):
    target = tmp_path / "render"
    assert main(["--demo", "--segments", str(target)]) == 0
    written = sorted(p.name for p in target.iterdir())
    assert written[0] == "01-cold-open.txt"
    assert written[-1] == "08-sign-off.txt"
    assert "[COLD OPEN]" not in (target / "01-cold-open.txt").read_text()


def test_cli_reads_a_kicker_file(tmp_path):
    kicker = tmp_path / "kicker.txt"
    kicker.write_text("A hedge fund sat in cash.", encoding="utf-8")
    out = tmp_path / "close.txt"
    assert main(["--demo", "--kicker-file", str(kicker), "--out", str(out)]) == 0
    assert "A hedge fund sat in cash." in out.read_text(encoding="utf-8")


def test_cli_warns_when_a_kicker_smuggles_in_digits(tmp_path, capsys):
    kicker = tmp_path / "kicker.txt"
    kicker.write_text("The fund returned 11 percent.", encoding="utf-8")
    assert main(["--demo", "--kicker-file", str(kicker)]) == 0
    assert "digits left in the script" in capsys.readouterr().err


def test_cli_merges_a_names_file_over_the_builtins(tmp_path):
    names = tmp_path / "names.json"
    names.write_text('{"ZZZZ": "Zed Industries"}', encoding="utf-8")
    out = tmp_path / "close.txt"
    # --demo bypasses the loader, so this exercises parsing and the merge only.
    assert main(["--demo", "--names", str(names), "--out", str(out)]) == 0
    assert out.exists()


def test_cli_date_overrides_the_rotation_seed(tmp_path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    main(["--demo", "--date", "2026-08-10", "--out", str(first)])
    main(["--demo", "--date", "2026-08-13", "--out", str(second)])
    assert first.read_text() != second.read_text()


def test_cli_rejects_a_malformed_date():
    with pytest.raises(SystemExit):
        main(["--demo", "--date", "13/08/2026"])


def test_cli_preview_prints_only_the_two_segments(capsys):
    assert main(["--demo", "--preview"]) == 0
    out = capsys.readouterr().out
    assert "[THE TAPE]" in out
    assert "[MOVERS]" in out
    assert "[SIGN-OFF]" not in out
    assert "[THE STRAIGHT BEAT]" not in out


def test_cli_preview_writes_to_out(tmp_path):
    out = tmp_path / "preview.txt"
    assert main(["--demo", "--preview", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "[THE TAPE]" in text
    assert "[KICKER]" not in text


def test_cli_preview_ignores_a_kicker(tmp_path, capsys):
    kicker = tmp_path / "kicker.txt"
    kicker.write_text("A parrot with a lawyer.", encoding="utf-8")
    assert main(["--demo", "--preview", "--kicker-file", str(kicker)]) == 0
    assert "A parrot with a lawyer." not in capsys.readouterr().out


def test_cli_preview_writes_two_numbered_segments(tmp_path):
    target = tmp_path / "render"
    assert main(["--demo", "--preview", "--segments", str(target)]) == 0
    assert sorted(p.name for p in target.iterdir()) == [
        "01-the-tape.txt",
        "02-movers.txt",
    ]


def test_cli_preview_reports_when_there_is_nothing_to_show(monkeypatch, capsys):
    monkeypatch.setattr(market, "demo_facts", lambda session=None: MarketFacts(DAY_TWO))
    assert main(["--demo", "--preview"]) == 1
    assert "no tape or movers data to preview" in capsys.readouterr().err
