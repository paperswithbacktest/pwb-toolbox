# Shared karaoke leaderboard

A small server so several people can post scores to one board. It serves
`static/karaoke-box.html` and the score API from the same origin, so a room
full of phones pointed at one host share a leaderboard.

Standard library only — no new dependencies, nothing to install.

Unrelated to the trading library; it exists purely to give the karaoke page
somewhere to post scores.

## Run it

```bash
python -m tools.karaoke_server
```

```
Karaoke board on http://localhost:8770  (scores in karaoke-scores.json)
Open that address on any device on the same network to share a board.
```

Open that address, turn on **Score me**, and sing. Anyone else on the same
network who opens the same address lands on the same board — the page
notices it was served by a board host and connects on its own.

Options:

```bash
python -m tools.karaoke_server --port 9000 --db /var/lib/karaoke.json
python -m tools.karaoke_server --host 127.0.0.1        # this machine only
python -m tools.karaoke_server --origin https://example.com
```

`--db` also reads from `KARAOKE_DB`. Set `KARAOKE_QUIET=1` to silence the
request log.

## Pointing a page somewhere else

A copy of the page opened straight from disk makes no requests at all. To
attach it to a server, paste the address into **Shared board** in the
leaderboard panel and press Connect. Blank means scores stay in that
browser.

Cross-origin requests are allowed (`--origin` sets the header, `*` by
default), so a page hosted elsewhere can post to a central server.

## API

| | |
|---|---|
| `GET /` | the karaoke page, wrapped as a document and told where the board is |
| `GET /api/scores?limit=20` | `{"scores": [...]}`, best first |
| `POST /api/scores` | one run as JSON; returns `{"entry": {...}, "scores": [...]}` |
| `GET /healthz` | `{"ok": true}` |

A run looks like:

```json
{
  "score": 87, "title": "Twinkle, Twinkle, Little Star", "name": "Ada",
  "code": "001", "rank": "Showstopper", "notes": 42, "hit": 37,
  "tempo": 100, "duet": false, "part": "a"
}
```

Only `score` (0–100) and `title` are required. Text is length-capped and
stripped of control characters, numbers are range-checked, and `at` is
assigned by the server — a client cannot backdate itself to win a tie.
Malformed runs get a 400 with a reason. The file keeps the best 500 runs.

## What this is not

There is no authentication. Anyone who can reach the port can post a score
or read the board, and nothing stops someone submitting a 100 they did not
sing. That is the right trade for a party on a home network and the wrong
one for the open internet — don't expose it publicly without putting
something in front of it.

Scores live in one JSON file. Back it up by copying it.
