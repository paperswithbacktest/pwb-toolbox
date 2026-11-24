# World Model

`pwb_toolbox.world_model` reads the PWB World Model — companies, their
identifiers over time, and the relations between them — **as it was knowable
at a date**. The tables are private datasets on the Hugging Face Hub:

| Dataset | Content |
|---|---|
| `WorldModel-Entities` | One row per version of an entity (name, type, country) |
| `WorldModel-Identifiers` | Tickers, CIKs, CUSIPs... mapped to an `entity_id`, with time intervals |
| `WorldModel-Edges-<Family>` | Relations between entities, one dataset per family |

Reading them needs a Hub token that can see them (`HF_ACCESS_TOKEN`, or
`huggingface-cli login`).

## The point-in-time rule

Every row carries two clocks:

- `known_at` — when the public could know it. At date T, a row with
  `known_at > T` does not exist: a correction published after T never changes
  what a backtest sees at T.
- `[valid_from, valid_to)` — when the row is true in the world. The interval is
  half-open: `valid_to` is the first day of the next state, and empty when the
  state is still open.

The tables are append-only. To read them at T, each key (an identifier, an
entity, an edge) keeps the rows of its **latest publication** with
`known_at <= T`; the answer is the row whose interval holds the date. A later
publication of a key replaces the earlier one — that is how an interval gets
closed or corrected.

`as_of` is turned into a knowledge cutoff this way:

- a date, or a midnight timestamp without timezone (a daily bar's index): the
  end of that day, New York time — a strategy deciding on that day's close
  may use what was published during the day;
- a timestamp with a time and no timezone: that instant, New York time;
- a timezone-aware timestamp: that instant.

## Resolving a ticker

```python
from pwb_toolbox import world_model as wm

wm.resolve("GOOGL", "2024-01-02")                # -> "E..." or None
wm.resolve("GOOGL", "2024-01-02", details=True)  # entity_id, cik, name, source, confidence, interval
wm.resolve("0001652044", "2024-01-02", scheme="cik")
```

`None` means the identifier does not resolve at that date with what was known
then; nothing is guessed. A ticker reused by two companies resolves to each at
its own dates.

`date=` tests the intervals on another day than `as_of`: today's knowledge of
who held a ticker years ago. That is research, not a backtest — it reads rows
published after that day.

## A whole panel

A backtest resolves a universe at every rebalance. Do it in one call:

```python
import pandas as pd

dates = pd.bdate_range("2015-01-01", "2020-12-31", freq="BME")
panel = wm.resolve_panel(["AAPL", "GOOGL", "DELL"], dates)   # one row per (ticker, date)
ids = panel.pivot(index="date", columns="ticker", values="entity_id")
```

Each date is its own knowledge cutoff, so the panel is point-in-time row by row.
`pairs=True` zips two equal-length sequences instead of crossing them; `as_of=`
fixes one cutoff for every row. The cost is linear in the number of rows read
and of queries: prefer it to calling `resolve` in a loop.

## The graph

```python
edges = wm.get_graph("2020-12-31", relations=["customer_of"])
```

Returns the edges (`src`, `dst`, `relation`, `weight`, `sign`, `valid_from`,
`valid_to`, `known_at`, `source`, `source_doc`, `confidence`, `method`,
`evidence`) knowable at `as_of` and true on its date. Each edge
`(src, dst, relation, method)` keeps its latest publication.

- `method=None` (or `"latest"`): for each relation, the extractor whose latest
  publication visible at `as_of` is the most recent; `"all"` keeps every
  method side by side; a name or a list selects them.
- `supplier_to` is derived from `customer_of` with `src` and `dst` swapped.
- `date=` tests the intervals on another day than `as_of`. An edge describing a
  past fiscal period is valid over that period, so asking for the period that
  was last reported may need an earlier `date`.

While no `WorldModel-Edges-<Family>` dataset is published, `get_graph` raises
`WorldModelNotAvailable` and says so.

## Pinning and local builds

```python
model = wm.WorldModel(revision={"WorldModel-Identifiers": "<commit sha>"})
model.resolve("GOOGL", "2024-01-02")
```

A backtest is reproducible from `(as_of, method, revision)`. Without a
revision, the current commit of each table is read and recorded by the
prepared-data cache.

`WorldModel(local_dir=...)`, or the `PWB_WORLD_MODEL_DIR` environment
variable, reads a local build instead of the Hub: one sub-directory per table,
holding the Parquet shards or several generations with a `manifest.json` each
(the newest is read). Shards are named after the year of `known_at`; a read
never opens a shard from after its cutoff.
