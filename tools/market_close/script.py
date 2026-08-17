"""Assemble a daily market-close script with Eleven v3 audio tags.

Three rules shape everything below.

**The generator reports moves; it never invents causes.** It has prices, not
press releases, so no line here asserts *why* anything happened. That sounds
like a limitation and is actually the joke: financial media's house style is
confident post-hoc explanation, so the humour lives in refusing to supply one.
"Somebody will tell you why — whoever tells you fastest will be the least
sure" needs no facts beyond the move itself, and so cannot go stale, be wrong,
or quietly turn into defamation on a day this runs unattended.

**The straight beat never rotates.** Every other segment picks from a bank so
a week of episodes doesn't repeat itself, but the disclaimer is a fixed
string. A show that reads real price levels in a comic register needs one, and
the persona already has a slot where it drops the act — which makes the
compliance requirement and the writing want the same thing.

**A line break in the output is a beat.** v3 treats whitespace as timing, so
none of the banks below wrap for source readability; they use implicit string
concatenation instead. Where a break appears in a rendered script it is there
because somebody wanted the pause.

Rotation is seeded by the session date, so a given day always renders the same
script (re-runnable, reviewable, testable) while consecutive days differ.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from . import spoken
from .market import MarketFacts, Quote

# --------------------------------------------------------------------------
# rotation
# --------------------------------------------------------------------------


def pick(options: list[str], seed: date, salt: str) -> str:
    """Choose deterministically from a bank, keyed by session date.

    Hashing rather than ``random`` so the choice survives process restarts and
    Python versions: the same date always renders the same script.
    """
    if not options:
        raise ValueError("empty option bank")
    digest = hashlib.sha256(f"{seed.isoformat()}:{salt}".encode()).digest()
    return options[int.from_bytes(digest[:8], "big") % len(options)]


# --------------------------------------------------------------------------
# banks
# --------------------------------------------------------------------------

COLD_OPEN = {
    "up": [
        "Stocks went up today. [pause] We'll spend the next four minutes "
        "pretending we know why.",
        "Green across the board tonight. [pause] Somewhere, a strategist is "
        "quietly deleting a note.",
        "Stocks rose today, and the explanations have already been written. "
        "[pause] They were written last week.",
        "Good news tonight, if you own things. [pause] Which is more or less "
        "the entire business model.",
    ],
    "down": [
        "Stocks fell today. [pause] The reasons will arrive tomorrow, fully "
        "formed and very confident.",
        "A red session tonight. [pause] Nobody saw it coming — according to "
        "the people who said they saw it coming.",
        "Stocks dropped today. [pause] This is called a healthy correction, "
        "[pause] by people who are not selling.",
        "Down day. [pause] I'd remind everyone the market has recovered from "
        "a hundred percent of previous declines… [pause] so far.",
    ],
    "mixed": [
        "Stocks closed mixed today, which is the phrase we use when we have "
        "no idea what happened.",
        "A mixed session tonight. Some things up, some things down. [pause] "
        "Riveting.",
        "Stocks went sideways today. [pause] Four minutes. [pause] Let's see "
        "what I can do with that.",
        "Mixed close tonight. [pause] Which means every headline you read "
        "about today will be technically true.",
    ],
}

BREADTH_NARROW = [
    "Volume was light, breadth was narrow, and the move was carried by a "
    'handful of names. [pause] Which we\'re calling "broad-based." [pause] '
    "Because we always do.",
    "More names fell than rose. [pause] On a day the index finished higher. "
    "[pause] Try not to think about that one too hard.",
    "The advance was narrow. [pause] A few very large companies had a nice "
    "afternoon, and everybody else came along for the photograph.",
    "Breadth was poor, which is the part that doesn't make the headline "
    "[pause] because it doesn't fit in the headline.",
]

BREADTH_BROAD = [
    "Breadth was healthy — most names participated. [pause] That's rarer "
    "than it sounds, and nobody will mention it tomorrow.",
    "The move was broad. [pause] Genuinely broad. [exhales] I'm as surprised "
    "as you are.",
    "Most things went the same direction today, which we call conviction "
    "[pause] and which is usually just everyone reading the same screen.",
    "Participation was wide tonight. [pause] Enjoy it. [pause] It doesn't " "last.",
]

GAINER_JOKES = [
    "[pause] By tomorrow morning there will be nine explanations for that, "
    "[pause] all written by people who did not own it yesterday.",
    "[pause] Somebody will tell you why. [pause] Whoever tells you fastest "
    "will be the least sure.",
    "[pause] The company has said nothing at all. [pause] This has slowed "
    "nobody down.",
    "[pause] [sarcastic] And of course everyone saw that coming. [pause] " "Obviously.",
]

LOSER_JOKES = [
    "[pause] The stock has an opinion. [pause] The press release will not.",
    "[pause] Nobody rings a bell at the top. [pause] They do, however, issue "
    "a statement about eleven hours later.",
    "[pause] I'm told there's a reason. [exhales] There's always a reason, "
    "and it always arrives after the move.",
    "[pause] If you held that today — [pause] I'm sorry. [pause] And also: "
    "position sizing.",
]

# Split by size: "a move of approximately nothing" is a good joke on three
# basis points and a wrong one on twenty.
RATE_JOKES_SMALL = [
    "[pause] That is a move of approximately nothing, [pause] which will not "
    "stop anybody writing four hundred words about it.",
    "[pause] Rates went essentially nowhere. [exhales] I've stopped asking.",
    "[pause] Traders will read something into that. [pause] Traders read "
    "something into EVERYTHING.",
]

RATE_JOKES_LARGE = [
    "[pause] The bond market spent the afternoon disagreeing with the stock "
    "market. [pause] One of them is wrong. [pause] Historically, it is not "
    "the bond market.",
    "[pause] That is a real move, [pause] and the people explaining it to you "
    "tonight will not agree with each other by morning.",
    "[pause] Somebody repriced something. [exhales] We'll find out what in "
    "about a week.",
]

CRUDE_JOKES = [
    '[pause] Analysts cited "demand concerns." [pause] There are always '
    "demand concerns. [pause] It's oil. [pause] Somebody is always concerned.",
    "[pause] They cite supply when it rises and demand when it falls, "
    "[pause] and nobody has ever once made them pick.",
    "[pause] Oil moved. [pause] Somewhere a very serious man is drawing a "
    "triangle on a chart about it.",
]

CRYPTO_JOKES = [
    "[pause] It was large, it happened quickly, and by the time this airs it "
    "will have happened again in the other direction.",
    "[pause] I am contractually obliged to tell you the number, [pause] and "
    "spiritually obliged to tell you it will be different by breakfast.",
    "[exhales] I have no further analysis. [pause] I'm not certain anybody " "does.",
]

SIGN_OFF = [
    "[pause] The market will do something tomorrow.\n"
    "[pause] We'll explain it afterward. [pause] Confidently.",
    "[pause] Same time tomorrow, [pause] where I will read you different "
    "numbers in an identical tone of voice.",
    "[pause] Go and do something that isn't this. [pause] The screen will "
    "still be here.",
    "[pause] Nothing that happened today will matter in ten years — [pause] "
    "which is either comforting or upsetting, [pause] depending entirely on "
    "your time horizon.",
]

# Fixed. See the module docstring: this is the one block that never rotates,
# and its line breaks are deliberate beats.
STRAIGHT_BEAT = """[sighs] And here's the part I say straight, because it actually matters.
Nothing in this broadcast is advice. Not one word of it. I am reading numbers
off a screen and making jokes about them — that is the entire job.
[pause] If you're putting real money at risk, the two things that survive
contact with reality are position sizing and time horizon. Everything else,
[pause] including me, [pause] is entertainment.

[pause] Okay. [exhales] Back to it."""

KICKER_PLACEHOLDER = (
    "<< Write the kicker by hand — one human-scale story, no numbers, landing\n"
    "   on [starts laughing]. It is the only segment this tool will not write\n"
    "   for you, and the only one anybody ever quotes back at you. Pass it\n"
    "   with --kicker-file to drop it in here. >>"
)

GAIN_VERBS = ("closed up", "gained", "added", "advanced")
LOSS_VERBS = ("closed down", "slipped", "shed", "gave up")

# Below this, a yield move is noise rather than news.
QUIET_RATE_MOVE_BP = 5.0


@dataclass
class ScriptOptions:
    anchor: str = "Max Brennan"
    show: str = "the Market Close"
    kicker: str | None = None


def _capitalize(text: str) -> str:
    """Upper-case the opening letter without touching the rest.

    ``str.capitalize`` would lower-case "S and P"; index names arrive
    sentence-cased for mid-sentence use and only the first one needs lifting.
    """
    return text[:1].upper() + text[1:] if text else text


# --------------------------------------------------------------------------
# segments
# --------------------------------------------------------------------------


def _index_clause(quote: Quote, position: int) -> str:
    """One index's move, in the unit that index is actually quoted in."""
    pct = quote.percent_change
    if abs(pct) < 0.05:
        return f"{quote.name} finished essentially flat"

    verbs = GAIN_VERBS if pct > 0 else LOSS_VERBS
    verb = verbs[position % len(verbs)]

    # The Dow is read in points on air; everything else in percent.
    if quote.symbol == "INDU":
        return f"{quote.name} {verb} {spoken.say_points(quote.point_change)}"

    magnitude = spoken.say_percent(pct)
    # An anchor states the unit once and then drops it: "the S and P closed up
    # six tenths of a percent. The Nasdaq gained nine tenths."
    if position > 0 and magnitude.endswith(" of a percent"):
        magnitude = magnitude[: -len(" of a percent")]
    return f"{quote.name} {verb} {magnitude}"


def cold_open(facts: MarketFacts, options: ScriptOptions) -> str:
    line = pick(COLD_OPEN[facts.direction], facts.session_date, "cold-open")
    dateline = spoken.say_date(facts.session_date)
    return (
        f"[COLD OPEN]\n\n"
        f"Good evening. I'm {options.anchor}, and this is {options.show} "
        f"for {dateline}.\n[pause] {line}"
    )


def tape(facts: MarketFacts) -> str | None:
    if not facts.indices:
        return None

    clauses = [
        _index_clause(quote, position) for position, quote in enumerate(facts.indices)
    ]
    body = ". ".join(_capitalize(clause) for clause in clauses) + "."

    bank = BREADTH_NARROW if facts.is_narrow else BREADTH_BROAD
    joke = pick(bank, facts.session_date, "breadth")

    counts = ""
    if facts.breadth_total >= 20:
        counts = (
            f"[pause] {_capitalize(spoken.int_to_words(facts.advancers))} names "
            f"rose, {spoken.int_to_words(facts.decliners)} fell.\n"
        )

    return f"[THE TAPE]\n\n{body}\n{counts}[pause] {joke}"


def movers(facts: MarketFacts) -> str | None:
    if facts.gainer is None and facts.loser is None:
        return None

    blocks = []

    if facts.gainer is not None:
        joke = pick(GAINER_JOKES, facts.session_date, "gainer")
        blocks.append(
            f"Shares of {facts.gainer.name} led the tape, up "
            f"{spoken.say_percent(facts.gainer.percent_change)}, closing at "
            f"{spoken.say_dollars(facts.gainer.close)}.\n{joke}"
        )

    if facts.loser is not None:
        joke = pick(LOSER_JOKES, facts.session_date, "loser")
        blocks.append(
            f"Going the other way — {facts.loser.name} finished down "
            f"{spoken.say_percent(facts.loser.percent_change)}, at "
            f"{spoken.say_dollars(facts.loser.close)}.\n{joke}"
        )

    return "[MOVERS]\n\n" + "\n\n".join(blocks)


def rates(facts: MarketFacts) -> str | None:
    if facts.rate is None:
        return None

    # Bond data arrives as a yield in percent, so a "point change" here is
    # percentage points and a basis point is a hundredth of one.
    basis_points = facts.rate.point_change * 100.0
    quiet = abs(basis_points) < QUIET_RATE_MOVE_BP

    if abs(basis_points) < 0.5:
        movement = f"was effectively unchanged, at {spoken.say_yield(facts.rate.close)}"
    else:
        direction = "eased" if basis_points < 0 else "rose"
        movement = (
            f"{direction} {spoken.say_basis_points(basis_points)} "
            f"to {spoken.say_yield(facts.rate.close)}"
        )

    bank = RATE_JOKES_SMALL if quiet else RATE_JOKES_LARGE
    joke = pick(bank, facts.session_date, "rates")
    return f"[RATES]\n\nTo the bond market. The ten-year yield {movement}.\n{joke}"


def commodities(facts: MarketFacts) -> str | None:
    if facts.crude is None and facts.crypto is None:
        return None

    blocks = []

    if facts.crude is not None:
        joke = pick(CRUDE_JOKES, facts.session_date, "crude")
        move = "up" if facts.crude.percent_change >= 0 else "down"
        blocks.append(
            f"Crude settled at {spoken.say_dollars(facts.crude.close)} a barrel, "
            f"{move} {spoken.say_percent(facts.crude.percent_change)}.\n{joke}"
        )

    if facts.crypto is not None:
        joke = pick(CRYPTO_JOKES, facts.session_date, "crypto")
        move = "higher" if facts.crypto.percent_change >= 0 else "lower"
        blocks.append(
            f"And Bitcoin — [exhales] Bitcoin went {move}, "
            f"{spoken.say_percent(facts.crypto.percent_change)}, to "
            f"{spoken.say_dollars(facts.crypto.close)}.\n{joke}"
        )

    return "[COMMODITIES]\n\n" + "\n\n".join(blocks)


def straight_beat() -> str:
    return f"[THE STRAIGHT BEAT]\n\n{STRAIGHT_BEAT}"


def kicker(options: ScriptOptions) -> str:
    body = options.kicker.strip() if options.kicker else KICKER_PLACEHOLDER
    return f"[KICKER]\n\nAnd finally tonight —\n\n{body}"


def sign_off(facts: MarketFacts, options: ScriptOptions) -> str:
    line = pick(SIGN_OFF, facts.session_date, "sign-off")
    return (
        f"[SIGN-OFF]\n\n"
        f"That's {options.show}. I'm {options.anchor}.\n{line}\n[pause] Goodnight."
    )


def render(facts: MarketFacts, options: ScriptOptions | None = None) -> str:
    """Build the full script. Segments with no data are dropped, not faked."""
    options = options or ScriptOptions()

    segments = [
        cold_open(facts, options),
        tape(facts),
        movers(facts),
        rates(facts),
        commodities(facts),
        straight_beat(),
        kicker(options),
        sign_off(facts, options),
    ]

    return "\n\n\n".join(segment for segment in segments if segment) + "\n"


def preview(facts: MarketFacts) -> str:
    """Just the tape and the movers — the segments carrying the figures.

    What is worth checking before you spend renders is the numbers, and nearly
    all of them live in these two blocks: index levels, breadth counts, two
    percentage moves and two closing prices. The jokes are the same either way,
    so a preview that dropped them would read differently from what ships;
    these are whole segments, exactly as they will be performed.

    Empty when neither segment has data, which the caller should treat as
    nothing to show rather than an empty script.
    """
    blocks = [block for block in (tape(facts), movers(facts)) if block]
    return "\n\n\n".join(blocks) + "\n" if blocks else ""


def split_segments(text: str) -> list[tuple[str, str]]:
    """Split a rendered script into ``(name, body)`` pairs.

    v3 holds a performance together better across a few sentences than across
    a whole broadcast, and a re-roll should cost one segment rather than the
    night's work — so the render workflow is segment-by-segment, and this is
    what feeds it.
    """
    pairs: list[tuple[str, str]] = []
    for block in text.split("\n\n\n"):
        block = block.strip()
        if not block:
            continue
        header, _, body = block.partition("\n")
        name = header.strip().strip("[]").lower().replace(" ", "-")
        pairs.append((name, body.strip()))
    return pairs
