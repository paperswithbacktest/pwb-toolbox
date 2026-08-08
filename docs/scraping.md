# Scraping trading scripts

`pwb_toolbox.scraping` collects trading-script source code from the web into a
local, deduplicated corpus you can mine for strategy ideas.

## PineScript and thinkScript are different languages

This trips people up often enough to state plainly:

| | PineScript | thinkScript |
| --- | --- | --- |
| Platform | TradingView | thinkorswim (Schwab) |
| Declaration | `strategy("…")` / `indicator("…")` | `declare lower;` |
| Variables | `fast = input.int(10)` | `input length = 14;` |
| Series access | `close[1]`, `ta.sma(close, n)` | `close[1]`, `Average(close, n)` |
| Usual extension | `.pine` | `.ts` |

thinkorswim does **not** run PineScript. If you remember a thinkorswim
community section where people posted studies, that was thinkScript — shared
either as `tos.mx` share links or as source on forums. The two dialects are
detected, parsed and stored separately here, and a converter for one will not
work on the other.

The `.ts` collision matters in practice: on GitHub, a `.ts` file is
overwhelmingly more likely to be TypeScript. `detect_language` therefore treats
the extension as a hint only and lets the content decide, rejecting anything
carrying TypeScript markers.

## Quick start

```python
from pwb_toolbox.scraping import GitHubSource, ScriptStore

source = GitHubSource()                 # reads GITHUB_TOKEN if set
store = ScriptStore("script-corpus")
store.extend(source.collect("owner/pinescript-collection"))

for record in store.records():
    print(record.language, record.kind, record.title, record.license)
```

Or from the command line:

```bash
python -m pwb_toolbox.scraping github owner/repo another/repo --out script-corpus
python -m pwb_toolbox.scraping tradingview https://www.tradingview.com/script/ID-Name/ --accept-terms
```

## What it will not collect

Two filters are on by default, and both can be turned off deliberately:

* **Non-permissive licenses.** `GitHubSource` reads the repository's SPDX
  license and raises `SkippedRepository` unless it is in `PERMISSIVE_LICENSES`.
  A repository with no license is all-rights-reserved, not public domain. Pass
  `require_license=False` (`--allow-any-license`) to override.
* **Code that says it is paid.** Both communities mix free and commercial
  scripts, and paid ones usually announce it in a header comment
  ("premium members only", "do not redistribute", "license key"). Files matching
  those markers are skipped and recorded in `source.warnings`. Pass
  `skip_commercial=False` (`--include-commercial`) to override.

The commercial filter reads comments, not intent — it catches the obvious
cases, not a paid script whose header says nothing.

## Fetching politely

`PoliteSession` wraps `requests` and is what every source uses:

* `robots.txt` is fetched once per host and consulted before every request.
  A missing file (4xx) means unrestricted, per RFC 9309; a **5xx or a network
  error means fully disallowed**, because an unreachable `robots.txt` is not
  permission.
* Requests to a host are spaced by `min_interval`, or the host's `Crawl-delay`
  when that is longer.
* `429` and `5xx` are retried with exponential backoff, honouring `Retry-After`.

`sleep` and `monotonic` are injectable, which is how the tests exercise pacing
without spending real time.

## TradingView

`TradingViewSource` requires `accept_terms=True` and takes one URL at a time —
there is no crawler that discovers pages on its own. That is deliberate.
TradingView licenses its site content for display and restricts automated
non-display use, and script authors retain rights in their code. Reading a
handful of open-source scripts you intend to study is defensible under those
terms; assembling a bulk corpus is not. Extracting a protected or invite-only
script is an IP violation and is not supported here.

## Verification status

Worth knowing before you rely on any of this:

* `languages`, `models`, `store` and `PoliteSession` are unit tested, and the
  robots/pacing layer has also been checked live against a real host.
* `GitHubSource` is tested against mocked API responses. The live GitHub API was
  not reachable from the environment this was written in, so the endpoint
  contract is taken from GitHub's documentation rather than confirmed.
* `TradingViewSource` is tested against synthetic fixtures only; TradingView was
  unreachable, so the live page structure is **unconfirmed**.
  `extract_pine_source` validates whatever it recovers with
  `looks_like_pinescript` and returns `None` on a mismatch, so a stale selector
  yields nothing rather than garbage — but expect to adjust it on first real use.
