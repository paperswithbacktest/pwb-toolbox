"""Run `pwb_toolbox.converting` over a tree of real `.pine` files and rank the gaps.

Finding converter bugs one at a time -- convert a script, hit a failure, fix it,
convert again -- is slow and biased towards whatever the last script happened to
use. This converts a whole corpus at once and orders the reasons by how many
scripts each one costs, so the next thing to work on is a measurement rather
than a guess.

Build a corpus by cloning a few permissively-licensed collections, then:

    python -m tools.pine_sweep /path/to/corpus
    python -m tools.pine_sweep /path/to/corpus --strategies-only

`--strategies-only` keeps files that declare `strategy(...)`. Worth using: an
indicator library can outnumber the strategies in a corpus ten to one and drag
the headline number somewhere meaningless, since this converter targets
strategies.

A crash is reported separately and loudly. `convert` is contracted never to
raise -- it reports what it cannot handle -- so a non-zero crash count is a bug
in the converter itself, not a fact about the corpus.
"""

import argparse
import collections
import pathlib
import re
import sys
import traceback

from pwb_toolbox.converting import convert

STRATEGY_RE = re.compile(r"^\s*strategy\s*\(", re.MULTILINE)

#: Reasons name the offending identifier, so `var entryPrice: ...` and
#: `var stopPrice: ...` describe one gap. Strip the specifics to group them.
_NORMALISE = (
    (re.compile(r"^(var|varip) \S+:"), r"\1 <name>:"),
    (re.compile(r"^could not parse: .*"), "could not parse"),
    (re.compile(r"^\S+: (reassignment|history of|a parameter)"), r"<name>: \1"),
    (
        re.compile(r"^unknown identifier '([a-z_]+)\.[^']*'"),
        r"unknown identifier '\1.*'",
    ),
    (re.compile(r"^unknown identifier '[^']*'"), "unknown identifier '<name>'"),
)


def normalise(reason: str) -> str:
    """Collapse a reason to the gap it describes, dropping the identifier."""
    for pattern, replacement in _NORMALISE:
        collapsed = pattern.sub(replacement, reason)
        if collapsed != reason:
            return collapsed
    return reason


def sweep(root: pathlib.Path, strategies_only: bool = False):
    """Convert every `.pine` under `root`, returning (clean, crashes, reasons)."""
    reasons = collections.Counter()
    sole_blocker = collections.Counter()
    crashes = []
    considered = 0
    clean = 0

    for path in sorted(root.rglob("*.pine")):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if strategies_only and not STRATEGY_RE.search(source):
            continue
        considered += 1
        try:
            result = convert(source)
        except Exception:
            crashes.append((path, traceback.format_exc().strip().splitlines()[-1]))
            continue
        if result.ok:
            clean += 1
            continue
        gaps = {normalise(item) for item in result.unsupported}
        reasons.update(gaps)
        if len(gaps) == 1:
            sole_blocker[next(iter(gaps))] += 1

    return considered, clean, crashes, reasons, sole_blocker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus", type=pathlib.Path)
    parser.add_argument(
        "--strategies-only",
        action="store_true",
        help="only files declaring strategy(...), which is what this converter targets",
    )
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args(argv)

    considered, clean, crashes, reasons, sole = sweep(
        args.corpus, strategies_only=args.strategies_only
    )
    if not considered:
        print(f"no .pine files under {args.corpus}")
        return 1

    scope = "strategies" if args.strategies_only else "scripts"
    print(
        f"{considered} {scope} | {clean} convert clean "
        f"({clean / considered:.0%}) | {len(crashes)} crash"
    )

    if crashes:
        print("\nCRASHES -- convert() is contracted never to raise:")
        for path, line in crashes[: args.top]:
            print(f"  {path.name}: {line}")

    blocked = considered - clean - len(crashes)
    if blocked:
        print(f"\nwhat blocks the other {blocked}, by scripts affected:")
        for reason, count in reasons.most_common(args.top):
            alone = sole.get(reason, 0)
            note = f"   ({alone} blocked by this alone)" if alone else ""
            print(f"  {count:4}  {reason}{note}")

    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main())
