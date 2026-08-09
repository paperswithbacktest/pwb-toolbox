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

## Layout

- `pwb_toolbox/` — the shipped package (`datasets`, `backtesting`, `execution`, `performance`)
- `pwb_toolbox_legacy/` — superseded code kept for reference; not part of the public API
- `tests/` — pytest suite
- `tools/ib_server/` — operational scripts for running strategies against Interactive Brokers
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
pytest tests/ -v                  # full suite (43 tests, ~4s)
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
