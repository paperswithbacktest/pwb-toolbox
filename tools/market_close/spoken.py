"""Turn market numbers into words a text-to-speech model will read correctly.

Eleven v3 reads digits and symbols by its own rules, and on a markets script
that is most of the runtime. ``4.09`` can come back as "four point zero nine"
when the desk says "four-oh-nine"; ``&`` is a coin flip between "and" and
silence; ``$71.40`` invites "dollar seventy-one point four". So nothing
numeric reaches the rendered script as digits — every figure goes through this
module first, and what ElevenLabs receives is already spelled the way it should
be said.

The idiom here is broadcast, not arithmetic. Sub-one-percent moves become
"six tenths of a percent" rather than "zero point six percent", quarters and
halves are named rather than decimalised, and hundreds lead with "a hundred"
rather than "one hundred" — because that is what a closing report actually
sounds like out loud.
"""

from __future__ import annotations

_UNITS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)

_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)

_SCALES = ((1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand"))

_ORDINALS = {
    1: "first",
    2: "second",
    3: "third",
    5: "fifth",
    8: "eighth",
    9: "ninth",
    12: "twelfth",
}


def _under_hundred(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] if ones == 0 else f"{_TENS[tens]}-{_UNITS[ones]}"


def _under_thousand(n: int, lead: bool) -> str:
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        return _under_hundred(rest)
    # "a hundred and forty points" only when the hundreds group opens the
    # number; mid-number it has to be "one thousand one hundred and forty".
    head = "a hundred" if (hundreds == 1 and lead) else f"{_UNITS[hundreds]} hundred"
    return head if rest == 0 else f"{head} and {_under_hundred(rest)}"


def int_to_words(value: int, lead: bool = True) -> str:
    """Spell an integer the way it is spoken aloud.

    ``lead`` controls the "a hundred" / "one hundred" choice; callers embedding
    the result mid-sentence rarely need to change it.
    """
    n = int(value)
    if n < 0:
        return f"negative {int_to_words(-n, lead)}"
    if n == 0:
        return "zero"

    parts: list[str] = []
    remaining = n
    first = True
    for scale, name in _SCALES:
        count, remaining = divmod(remaining, scale)
        if count:
            parts.append(f"{_under_thousand(count, lead and first)} {name}")
            first = False

    if remaining:
        if parts and remaining < 100:
            parts.append(f"and {_under_hundred(remaining)}")
        else:
            parts.append(_under_thousand(remaining, lead and first))

    return " ".join(parts)


def ordinal_to_words(day: int) -> str:
    """Spell a day-of-month as an ordinal, for the dateline."""
    n = int(day)
    if n in _ORDINALS:
        return _ORDINALS[n]
    if n < 20:
        return f"{_UNITS[n]}th"
    tens, ones = divmod(n, 10)
    if ones == 0:
        return f"{_TENS[tens][:-1]}ieth"
    return f"{_TENS[tens]}-{_ORDINALS.get(ones, _UNITS[ones] + 'th')}"


def say_percent(pct: float) -> str:
    """A percentage move in desk idiom. Sign is ignored.

    The direction belongs to the verb the caller chooses ("gained", "slipped"),
    so this returns magnitude only.
    """
    p = abs(float(pct))

    if p >= 1:
        rounded = round(p, 1)
        whole = int(rounded)
        frac = int(round((rounded - whole) * 10))
        if frac == 0:
            return f"{int_to_words(whole)} percent"
        if frac == 5:
            return f"{int_to_words(whole)} and a half percent"
        return f"{int_to_words(whole)} point {int_to_words(frac)} percent"

    # Quarters and halves read better than the tenths grid at these three
    # points — nobody says "two and a half tenths of a percent".
    for value, phrase in (
        (0.25, "a quarter percent"),
        (0.5, "half a percent"),
        (0.75, "three quarters of a percent"),
    ):
        if abs(p - value) < 0.025:
            return phrase

    tenths = int(round(p * 10))
    if tenths <= 0:
        return "a fraction of a percent"
    if tenths == 1:
        return "a tenth of a percent"
    return f"{int_to_words(tenths)} tenths of a percent"


def say_points(value: float) -> str:
    """An index move in points. Sign is ignored."""
    n = abs(int(round(value)))
    return "one point" if n == 1 else f"{int_to_words(n)} points"


def say_level(value: float) -> str:
    """An index level, rounded to whole points."""
    return int_to_words(int(round(value)))


def say_yield(rate: float) -> str:
    """A bond yield the way a desk quotes it: 4.09 becomes "four-oh-nine"."""
    r = float(rate)
    whole = int(r)
    cents = int(round((r - whole) * 100))
    if cents >= 100:  # e.g. 4.996 rounding up into the next whole number
        whole += 1
        cents = 0
    if cents == 0:
        return f"{int_to_words(whole)} percent"
    if cents < 10:
        return f"{int_to_words(whole)}-oh-{int_to_words(cents)}"
    return f"{int_to_words(whole)}-{_under_hundred(cents)}"


def say_basis_points(value: float) -> str:
    """A yield change in basis points. Sign is ignored."""
    n = abs(int(round(value)))
    return "one basis point" if n == 1 else f"{int_to_words(n)} basis points"


def say_dollars(amount: float) -> str:
    """A price in dollars.

    Cents are spoken below a thousand and dropped above it — "seventy-one
    dollars and forty cents" is a barrel of crude, but nobody reads bitcoin to
    the penny on air.
    """
    a = abs(float(amount))
    if a >= 1000:
        return f"{int_to_words(int(round(a)))} dollars"

    whole = int(a)
    cents = int(round((a - whole) * 100))
    if cents >= 100:
        whole += 1
        cents = 0
    if cents == 0:
        return f"{int_to_words(whole)} dollars"
    return f"{int_to_words(whole)} dollars and {int_to_words(cents)} cents"


def say_ticker(symbol: str) -> str:
    """Spell a ticker letter by letter, which is how it is read on air.

    Spaces rather than hyphens: v3 renders "N V D A" as four letters and
    "NVDA" as an attempted word.
    """
    return " ".join(ch for ch in str(symbol).upper() if ch.isalnum())


_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def say_date(value) -> str:
    """A dateline: "Thursday, August thirteenth"."""
    weekday = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )[value.weekday()]
    return f"{weekday}, {_MONTHS[value.month - 1]} {ordinal_to_words(value.day)}"
