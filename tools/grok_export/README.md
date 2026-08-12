# grok_export

Export your Grok (grok.com) chat history to raw JSON and readable Markdown.

Two routes in, one layout out. Use `pull` when you want your chats now; use
`convert` when you would rather go through xAI's sanctioned data download. Both
land in the same place, so you can start with one and switch later.

## What you get

```
grok-export/
├── index.json                                  # id, title, dates, message count
├── raw/<conversation-id>.json                  # every payload, verbatim
└── markdown/2026-07-14-pairs-trading-7f3a1.md  # the readable copy
```

`raw/` is the archive of record. The endpoints behind grok.com are internal and
undocumented, so the Markdown renderer guesses at field names — `raw/` keeps the
original bytes regardless, and `render` rebuilds the Markdown from it offline
once a guess is corrected. A misread field costs you formatting, never a message.

## Route 1: pull from a signed-in session

Grok has no per-conversation export button, so this reuses your browser's
cookies.

1. Open [grok.com](https://grok.com) signed in.
2. DevTools → **Network**, then click any conversation.
3. Right-click a request to `grok.com` → **Copy as cURL**.
4. Save it: `pbpaste > ~/grok-curl.txt` (macOS) or paste into a file.

```bash
python -m tools.grok_export probe --cookie ~/grok-curl.txt   # confirm it works
python -m tools.grok_export pull  --cookie ~/grok-curl.txt
```

`probe` fetches a single page and prints it raw. Run it first — it tells you
whether the endpoint and your cookies are good before a full crawl, and it is
what you read to fix a field-name guess.

The cookie can also come from `$GROK_COOKIE`, and `--cookie` accepts the cookie
string itself. Only cookie *names* are ever logged, never values.

`pull` is re-runnable: conversations already in `raw/` are skipped, so a second
run only picks up what is new. Pass `--refresh` to re-fetch everything.

Useful flags: `--limit N` to stop early, `--delay` for the gap between requests
(0.5s default — please leave it polite), `--no-markdown` for JSON only.

## Route 2: convert the official xAI export

Request a download at [accounts.x.ai/data](https://accounts.x.ai/data), wait for
the mail, then:

```bash
python -m tools.grok_export convert ~/Downloads/xai-export.zip
```

Slower to arrive, but sanctioned and stable — and this route is verified against
a real download. Takes the `.zip`, a directory, or a single `.json`/`.jsonl`
file.

The chats live in `prod-grok-backend.json`, shaped like this:

```jsonc
{"conversations": [{
  "conversation": {"id": …, "title": …, "create_time": "2026-07-28T00:29:26Z"},
  "responses": [{"response": {"message": …, "sender": "human",
                              "create_time": {"$date": {"$numberLong": "…"}}},
                 "share_link": …}]}]}
```

Two things that layout does are worth knowing, because both are handled and
both would otherwise silently drop data: the metadata sits under a
`conversation` wrapper while the turns sit beside it, and each turn is wrapped
again under `response`, so `sender` and `create_time` are two levels down.
Turn timestamps are MongoDB extended JSON rather than the ISO strings used at
the conversation level.

The reader still walks the whole tree looking for conversation-shaped objects
rather than hard-coding that path, so a re-organised dump generally keeps
working.

## Merging duplicates and repeated topics

Chat histories accumulate the same thread several times — the identical question
re-asked months later, or one topic picked up across four sittings.

```bash
python -m tools.grok_export merge --out grok-export --dry-run   # report only
python -m tools.grok_export merge --out grok-export             # write them
```

Writes `merged/`, one chronological document per topic, next to `markdown/`.
Byte-identical conversations collapse to the earliest copy. Originals are never
touched, and re-running is idempotent — the directory always holds exactly the
current grouping.

Similarity is TF-IDF cosine over title and message tokens, clustered
single-link. `--threshold` tunes it: **0.26** by default, lower merges more.
That default is tuned against a real 29-conversation export, where below ~0.22
unrelated matters chained together through shared vocabulary and above ~0.30
genuine continuations stopped matching. Run `--dry-run` first and read the
grouping before trusting it on a different history.

### Daily

`run_daily.sh` re-merges the local export and stays quiet unless the grouping
changed, so it is safe to leave in cron:

```
7 8 * * *  /path/to/pwb-toolbox/tools/grok_export/run_daily.sh
```

It also folds in any new xAI download sitting beside the export or in
`~/Downloads` before merging. Set `GROK_EXPORT_DIR` to point somewhere other
than `grok-export/`.

## When it breaks

It will, eventually — `pull` rides on endpoints xAI can change without notice.

| Symptom | Fix |
| --- | --- |
| `rejected the session cookie` / HTML instead of JSON | The session expired. Re-copy the cURL command. |
| `No list endpoint answered` | The path moved. Find the real one in DevTools and pass `--list-path` / `--detail-path` (the latter needs `{id}`). |
| Markdown is empty but `raw/` has content | A field name changed. Add the real key to the `*_KEYS` tuples in `schema.py`, then `python -m tools.grok_export render`. |
| `no id field recognised` from `probe` | Same fix, for `ID_KEYS`. |

Nothing here needs a re-crawl: `render` rebuilds from `raw/` without touching
the network.

## Notes

- `grok-export/` is gitignored. Your chats are private — keep them that way.
- This is an operational script, like `tools/ib_server`; it is not part of the
  shipped `pwb_toolbox` package. Its only dependency, `requests`, is already in
  `requirements.txt`.
- The official xAI API (`api.x.ai`) is a stateless completions API. It cannot
  see grok.com web chat history, which is why this exists.
- Tests are offline: `pytest tests/test_grok_export.py -v`.
