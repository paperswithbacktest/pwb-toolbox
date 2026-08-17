"""Command line interface for the daily market-close script generator.

    python -m tools.market_close --demo
    python -m tools.market_close --preview
    python -m tools.market_close --kicker-file kicker.txt --out close.txt
    python -m tools.market_close --segments render/

``--segments`` is the one worth knowing about: it writes the script out one
numbered file per block, which is the order you paste them into ElevenLabs.
``--preview`` is the one you'll type most: tape and movers only, to check the
figures read correctly before committing to a render.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from . import market, script
from .script import ScriptOptions


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected a date as YYYY-MM-DD, got {value!r}"
        ) from exc


def _load_names(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} should hold a JSON object of ticker -> spoken name")
    return {str(k): str(v) for k, v in data.items()}


def warn_on_digits(text: str) -> list[str]:
    """Report lines that still carry digits.

    The whole point of ``spoken.py`` is that ElevenLabs never sees a numeral,
    so anything surviving to here is either a hand-written kicker or a bug —
    and both are worth seeing before you spend a render on them.
    """
    return [
        line.strip() for line in text.splitlines() if any(c.isdigit() for c in line)
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.market_close",
        description="Generate a daily market-close script with Eleven v3 audio tags.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="use a canned session instead of loading data (no network, no credentials)",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        help="session date, which also seeds the joke rotation (default: the data's latest)",
    )
    parser.add_argument(
        "--kicker-file",
        type=Path,
        help="hand-written kicker to drop into the [KICKER] slot",
    )
    parser.add_argument(
        "--names",
        type=Path,
        help="JSON object mapping ticker -> spoken company name, merged over the built-ins",
    )
    parser.add_argument("--anchor", default="Max Brennan", help="anchor name")
    parser.add_argument("--show", default="the Market Close", help="programme name")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="show only the tape and movers, for checking the numbers",
    )
    parser.add_argument(
        "--out", type=Path, help="write the script here (default: stdout)"
    )
    parser.add_argument(
        "--segments",
        type=Path,
        metavar="DIR",
        help="also write one numbered file per segment, in render order",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    names = _load_names(args.names)
    if names is not None:
        names = {**market.COMPANY_NAMES, **names}

    if args.demo:
        facts = market.demo_facts(args.date)
    else:
        facts = market.collect(names=names)
        if args.date is not None:
            facts.session_date = args.date

    kicker = None
    if args.kicker_file is not None:
        kicker = args.kicker_file.read_text(encoding="utf-8")

    if args.preview:
        text = script.preview(facts)
        if not text:
            _log("no tape or movers data to preview")
            return 1
    else:
        text = script.render(
            facts,
            ScriptOptions(anchor=args.anchor, show=args.show, kicker=kicker),
        )

    offenders = warn_on_digits(text)
    if offenders:
        _log(
            "warning: digits left in the script — ElevenLabs will read these by "
            "its own rules, not yours. Spell them out:"
        )
        for line in offenders[:5]:
            _log(f"  {line}")

    if args.segments is not None:
        args.segments.mkdir(parents=True, exist_ok=True)
        for position, (name, body) in enumerate(script.split_segments(text), start=1):
            target = args.segments / f"{position:02d}-{name}.txt"
            target.write_text(body + "\n", encoding="utf-8")
        _log(f"wrote segments to {args.segments}/")

    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
        _log(f"wrote {args.out}")
    else:
        print(text, end="")

    return 0
