# pwb-toolbox

A toolbox library for quant traders: datasets, backtesting (Backtrader), live
execution, and performance analytics. Requires Python 3.10+.

## Flagging action items

Anything the user has to do themselves — export a key, restart something, click
through an OAuth flow, make a decision — goes in a dedicated block at the very end
of the reply, never buried in a paragraph:

```
## 🔴 NEEDS YOU

1. **Export the key** — `export API_KEY_21ST=...` in your shell profile
2. **Restart Claude Code** so it picks up the new env
```

Rules: one block per reply, always last, always that exact `## 🔴 NEEDS YOU`
heading so it is skimmable. Numbered steps in the order they must happen, each
leading with a bolded imperative. If a step is also explained in the prose above,
it still gets repeated here — the block is the checklist of record. No block at all
when nothing is needed; do not pad it with optional suggestions, or it stops
meaning anything.

Commands in that block get pasted into **Windows PowerShell**, so write them for
PowerShell rather than bash. No `curl … | sed` pipelines — `curl` is an alias for
`Invoke-WebRequest` there and takes different arguments, and `sed` does not exist.
No `~` for the home directory (use `$HOME`), and no `&&` chaining, which Windows
PowerShell 5.1 rejects. When the text being written contains em dashes or emoji,
append with `[IO.File]::AppendAllText(..., (New-Object Text.UTF8Encoding $false))` —
`Add-Content` defaults to ANSI on 5.1 and mangles them. Pin any
`raw.githubusercontent.com` URL to a commit SHA rather than to `main`: a branch that
has not merged yet still serves the old file, so the command silently does nothing.

Each step is one self-contained paste, and each step names the program it goes into
and how to open it. "Export the key" is not a step; "Open PowerShell (`Win`+`R`, type
`powershell`, press Enter), then paste this" is. Assume the reader does not know which
application a given command belongs in, and does not want to work it out — that
assumption is the whole point of the block. Never split one command across two
numbered items, and never wrap a command in prose they have to reassemble. Where it
helps, say what success looks like, so a step that prints nothing is not mistaken for
a step that failed.

If a step happens in a GUI rather than a shell, describe it with the same
specificity: name the window, the menu path, and the button text. Claude cannot open
anything on the user's machine — it runs in a remote container — so the directions
have to stand on their own.

Never ask the user to hand-edit a command to insert a value. Told to "swap in your
key," they reasonably paste the key on its own line, and PowerShell tries to run it
as a command. Prompt for it instead — `$k = Read-Host 'Paste your key'` — and use
`$k` in the next line. That also keeps the secret out of PSReadLine's history file,
which records every line entered at the prompt in plaintext, failed ones included.
Same rule for any placeholder, secret or not: the paste must work verbatim.

A full block looks like this:

````
## 🔴 NEEDS YOU

1. **Open PowerShell** — press `Win`+`R`, type `powershell`, press Enter. A window
   opens with a `PS C:\Users\you>` prompt.
2. **Set the key** — paste this one line, swapping in your real key, then press Enter:
   ```powershell
   [Environment]::SetEnvironmentVariable('API_KEY_21ST','your-key-here','User')
   ```
   It prints nothing when it works.
3. **Restart Claude Code** — close that terminal window entirely and open a new one,
   then run `/mcp` and choose `21st` from the list. Windows that were already open
   will not see the new variable.
````

## Layout

- `pwb_toolbox/` — the shipped package (`datasets`, `backtesting`, `execution`, `performance`)
- `pwb_toolbox_legacy/` — superseded code kept for reference; not part of the public API
- `tests/` — pytest suite
- `tools/ib_server/` — operational scripts for running strategies against Interactive Brokers
- `tools/grok_export/` — exports grok.com chat history to JSON/Markdown (`python -m tools.grok_export`)
- `docs/` — `datasets.md`, `backtesting.md`, `execution.md`

## Environment

Dependencies live in `requirements.txt`; `requirements-dev.txt` adds `pytest`.
CI (`.github/workflows/tests.yml`) runs `pip install -r requirements-dev.txt`
then `pytest tests/ -v` on Python 3.11.

In Claude Code on the web, `.claude/hooks/session-start.sh` does this setup
automatically: it builds a `.venv/` (the system interpreter has Debian-managed
packages such as `cryptography` that pip cannot upgrade), installs
`requirements-dev.txt` plus `black`, and exports `PATH` and `PYTHONPATH` so
bare `python`, `pytest`, and `black` resolve to that venv. The hook is a no-op
in local sessions, which manage their own environment.

It runs asynchronously, so the session is usable immediately while packages
install in the background — roughly a minute on a cold container, ~2s once it
is warm. If `pytest` or an import of a third-party package fails in the first
moments of a session, the install is most likely still running; re-run the
command rather than treating it as a real failure.

To set the same thing up by hand:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt black
export PYTHONPATH="$PWD"
```

The tests import `pwb_toolbox` from the repo root rather than from an installed
distribution. `pythonpath = ["."]` under `[tool.pytest.ini_options]` in
`pyproject.toml` covers that for `pytest` itself (including in CI, which sets no
`PYTHONPATH`); the exported `PYTHONPATH` above covers ad-hoc invocations such as
`python -c "import pwb_toolbox"`.

## Commands

```bash
pytest tests/ -v                  # full suite (170 tests, ~20s cold / ~3s warm)
pytest tests/test_optimal_limit_order.py -v
black pwb_toolbox/                # format; the repo is black-formatted
black --check --diff pwb_toolbox/ # check without writing
```

## Conventions

- Formatting is `black` with default settings — see `.vscode/settings.json`,
  which also enables pylint with `--disable=relative-beyond-top-level`.
- Tests must not require network access or a live broker. `ib_insync` calls are
  exercised against a mocked `IB` client (see `tests/test_ib_connector_calibration.py`),
  and dataset tests should not depend on `PWB_API_KEY` or a Hugging Face login.
- Regression tests for fixed bugs pin the previous numeric output where the old
  behavior must be preserved (see `_LEGACY_DEFAULT_QUOTE` in
  `tests/test_optimal_limit_order.py`).

## Design tooling (UI/UX)

`.claude/skills/` vendors the MIT-licensed
[ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) suite,
installed with `npx ui-ux-pro-max-cli init --ai claude`. It is unrelated to the
trading library — the package itself is headless — and exists only so sessions in
this repo can build dashboards, docs pages, and report UIs to a consistent
standard. Nothing under `pwb_toolbox/` imports it, and `pytest` never touches it.

The core skill is a local CSV database (84 UI styles, 192 color palettes, 74 font
pairings, 98 UX guidelines, 25 chart types, 22 stacks) queried with stdlib Python
— no network, no API key:

```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "saas landing page" --domain style
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "fintech dashboard" --domain color --json
```

The SKILL.md frontmatter says "67 styles, 161 palettes" — that string is hardcoded
in the upstream template and lags the shipped CSVs. Trust the data files.

`docs/index.html` is a landing page built entirely from those queries — palette,
font pairing and motion timings all came from the skill rather than being invented.
It is a single self-contained file: both typefaces are embedded as base64 woff2, so
it opens from `file://` with no build step and no network, which is also why it is
~120 KB. Rebuilding means re-querying the skill, not editing the base64 by hand.
GitHub Pages can serve it as-is from the `/docs` folder.

The installer also drops six companion skills (`design`, `design-system`,
`ui-styling`, `brand`, `slides`, `banner-design`) alongside the main one. They were
removed deliberately — several of their generators shell out to `npx shadcn` or
image APIs and none were needed here. Re-running `uipro init` restores them, so
prune again after any upgrade.

`.mcp.json` registers 21st.dev's [21st MCP](https://21st.dev/mcp) (the successor to
Magic MCP) for generating React/Tailwind components. It is an HTTP server
authenticated with `${API_KEY_21ST}` — never hardcode the key in `.mcp.json`.

Claude Code expands `${...}` from its own process environment and does not read
`.env`, so exporting the key in your shell profile (or `set -a; . .env; set +a`
before launching) is what actually works:

```bash
export API_KEY_21ST=...   # https://21st.dev/settings/api-keys
```

Without that variable the server fails to authenticate; nothing else in the repo
is affected.

## Credentials

`load_dataset` reads `PWB_API_KEY`, falling back to the Hugging Face Hub and
then to yfinance. Never commit keys; `.env` is gitignored.

`API_KEY_21ST` (21st.dev, from https://21st.dev/settings/api-keys) is read from the
environment by `.mcp.json`. Never commit keys; `.env` is gitignored.

`.env.example` lists both variables. Copy it to `.env` and fill it in — but note
that `.env` alone does not reach `.mcp.json`, which reads the process environment;
see the export note above.
