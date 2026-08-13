# market_close

Generates a daily market-close broadcast script for a text-to-speech talking-head
avatar. It reads a session out of `pwb_toolbox.datasets`, reduces it to facts, and
renders a script with Eleven v3 audio tags — with every number already spelled the
way it should be spoken.

```bash
python -m tools.market_close --demo                        # canned session, no credentials
python -m tools.market_close --preview                     # tape and movers only
python -m tools.market_close --kicker-file kicker.txt --out close.txt
python -m tools.market_close --segments render/            # one file per block
```

## The daily loop

1. `python -m tools.market_close --preview` — check the figures read correctly
   before committing to anything.
2. `python -m tools.market_close --kicker-file kicker.txt --segments render/`
3. Read it once out loud. The generator writes seven segments; you write the eighth.
4. Paste `render/01-…` through `render/08-…` into ElevenLabs Text to Speech one at a
   time, on **Eleven v3**, stability **Natural**.
5. Stitch the clips, drop the track onto a HeyGen avatar as uploaded audio.

Step 1 exists because the tape and movers carry nearly every number in the
broadcast — index levels, breadth counts, two percentage moves, two closing prices.
They are also the segments that change most between sessions, so an unfamiliar
ticker spelling or an odd-sounding level shows up there first. `--preview` prints
those two blocks exactly as they will be performed, jokes included, so what you
audition is what ships. It exits non-zero when there is nothing to show, which
makes it usable as a guard in a scheduled run.

Rendering segment by segment is not fussiness. v3 holds a performance together
better across a few sentences than across a whole broadcast, and a bad take on the
kicker should cost you one re-roll rather than the night's work.

## Why there are no digits in the output

ElevenLabs reads numerals by its own rules, and on a markets script that is most of
the runtime: `4.09` comes back as "four point zero nine" when the desk says
"four-oh-nine", `&` is a coin flip, `$71.40` invites "dollar seventy-one point four".

So `spoken.py` spells everything before it reaches the page, in broadcast idiom
rather than arithmetic — "six tenths of a percent", not "zero point six percent";
"a hundred and forty points", not "one hundred forty". A test asserts the rendered
script contains no digit at all, and the CLI warns if one survives, which in
practice means you typed one into the kicker.

## Why it never says why

The generator has prices. It does not have press releases, and it will not pretend
to: no line asserts a *cause* for any move. This matters more the more automated the
show gets — a template that fills in "after the company beat expectations" is a
template that will eventually broadcast something false about a real company, on a
day nobody is reading the output.

It also happens to be funnier. Financial media's house style *is* confident post-hoc
explanation, so the joke writes itself out of the refusal:

> Shares of Nvidia led the tape, up fourteen percent.
> [pause] Somebody will tell you why. [pause] Whoever tells you fastest will be the
> least sure.

That needs no facts beyond the move, cannot go stale, and cannot become defamation.

## The straight beat

One segment never rotates: the disclaimer. A show that reads real price levels in a
comic register needs one, and burying it in on-screen small print is the version
nobody hears. The persona already has a slot where it drops the act for fifteen
seconds — putting it there means the compliance requirement and the writing want the
same thing, and the disclaimer lands as the most sincere moment in the episode.

If you change one string in this package, don't let it be that one.

## Rotation

Every other segment picks from a bank of three or four lines, seeded by a hash of
the session date. So a given day always renders the same script — re-runnable,
reviewable, diffable — while a working week doesn't repeat itself. The jokes live in
the transitions rather than in the numbers, which is what lets fresh data drop into
the same skeleton without the comedy going with it.

Add lines to the banks in `script.py` freely; they're plain lists. Keep them as
single strings — a line break in the output is a beat, so the banks use implicit
string concatenation rather than wrapping for source readability.

## Options

| flag | effect |
|------|--------|
| `--demo` | canned session; no network, no `PWB_API_KEY` |
| `--date YYYY-MM-DD` | override the session date, which also reseeds the rotation |
| `--kicker-file PATH` | hand-written kicker for the `[KICKER]` slot |
| `--names PATH` | JSON `{"TICKER": "spoken name"}`, merged over the built-ins |
| `--anchor`, `--show` | rename the anchor and the programme |
| `--preview` | tape and movers only; exits `1` when neither has data |
| `--out PATH` | write the script (default: stdout) |
| `--segments DIR` | also write one numbered file per block, in render order |

`COMPANY_NAMES` in `market.py` covers about sixty large caps. Anything absent gets
its ticker spelled out — "Z Z Z Z" — which is also how a desk reads an unfamiliar
one, but `--names` is there for when you want fuller coverage.

## Layout

- `spoken.py` — numbers to broadcast English. No dependencies, heavily tested.
- `market.py` — dataset loading and reduction. `collect()` is the only function that
  touches the network; everything else is pure and takes a DataFrame, which is what
  keeps the suite offline.
- `script.py` — the template, the joke banks, and the rotation.
- `cli.py` — argument handling and the digit check.
