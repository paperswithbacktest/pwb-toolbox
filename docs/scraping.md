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
either as `tos.mx` share links or as source on forums, and covered by
`ThinkorswimSource` and `ForumSource` respectively. The two dialects are
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
python -m pwb_toolbox.scraping thinkorswim http://tos.mx/aBcDeFg
python -m pwb_toolbox.scraping forum https://usethinkscript.com/threads/some-study.42/ --max-pages 5
python -m pwb_toolbox.scraping tradingview https://www.tradingview.com/script/ID-Name/ --accept-terms
```

## The thinkorswim sources

Two collectors cover where thinkScript actually circulates.

**`ThinkorswimSource`** reads `tos.mx` share links — thinkorswim's own export
mechanism, where an author turns a study into a short link meant to be handed
to someone else. Because a share link exists precisely to be opened by another
person, this one is not gated behind a terms flag the way TradingView is. It
still honours `robots.txt` and still takes one link at a time.

```python
from pwb_toolbox.scraping import ThinkorswimSource, ScriptStore

source = ThinkorswimSource()
store = ScriptStore("script-corpus")
record = source.fetch("http://tos.mx/aBcDeFg")
if record is not None:
    store.add(record)
print(source.warnings)   # why anything was skipped
```

**`ForumSource`** walks a thread and collects the studies posted in it,
attributing each to its author and permalink:

```python
from pwb_toolbox.scraping import ForumSource

for record in ForumSource(max_pages=5).collect(thread_url):
    print(record.author, record.language, record.kind, record.url)
```

It is not written against any one forum. Posts are found through common
container conventions (`article`, `.message`, `data-author`), code through
standard `<pre>`/`<code>` plus the BBCode wrappers the usual engines emit, and
pagination through the standard `rel="next"` relation. A site doing none of
those yields nothing rather than nonsense.

Two filters matter more here than anywhere else, because forum threads are
mostly prose:

- Every candidate must pass `classify()` — real thinkScript or PineScript — so
  quoted replies, shell snippets and navigation text never become records.
- `min_chars` (default 60) drops the one-line fragments people quote
  mid-discussion.

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

* **Pages that are gated.** `looks_paywalled` recognises a page telling you to
  log in or upgrade, and the collector records a warning instead of storing
  whatever the teaser happened to render.

The commercial filter reads comments, not intent — it catches the obvious
cases, not a paid script whose header says nothing.

The gated-page and commercial checks are deliberately kept apart:
`looks_paywalled` strips code blocks before matching, so a freely posted study
whose header comment happens to read "paid members only" is reported as a
commercial *script*, not as a gated *page*. Both get rejected either way; the
difference is that the warning tells you which, and that is what makes an empty
corpus diagnosable.

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

* `languages`, `models`, `store`, `extract` and `PoliteSession` are unit tested,
  and the robots/pacing layer has also been checked live against a real host.
* `GitHubSource` is tested against mocked API responses. The live GitHub API was
  not reachable from the environment this was written in, so the endpoint
  contract is taken from GitHub's documentation rather than confirmed.
* `TradingViewSource`, `ThinkorswimSource` and `ForumSource` are tested against
  synthetic fixtures only. All of tradingview.com, tos.mx and
  usethinkscript.com were unreachable, so their live page structures are
  **unconfirmed**.

That last point is why none of the HTML collectors trust a selector. Each one
validates what it recovered — `looks_like_pinescript`, `looks_like_thinkscript`,
`classify` — and returns `None` or skips the block on a mismatch. A stale
selector therefore produces an empty corpus and a warning, not a corpus full of
page furniture. Expect to widen `CODE_SELECTORS` or `SOURCE_KEYS` in
`extract.py` on first real use; that is the intended adjustment point.
