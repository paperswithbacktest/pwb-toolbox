#!/bin/bash
# SessionStart hook: prepare a Claude Code on the web container so that
# `pytest` and `black` work against pwb_toolbox without any manual setup.
#
# Mirrors .github/workflows/tests.yml (pip install -r requirements-dev.txt)
# and adds the formatter the repo already assumes in .vscode/settings.json.
set -euo pipefail

# Local sessions manage their own environment (conda/.venv); only set up
# the ephemeral remote container. Must stay ahead of the async handshake
# below so local sessions exit without claiming a background slot.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Run in the background so the session is usable immediately. A cold install
# takes ~1 minute; the 5-minute timeout leaves room for a slow index.
echo '{"async": true, "asyncTimeout": 300000}'

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

VENV="$PROJECT_DIR/.venv"

# Install into a virtualenv rather than the system interpreter: several
# transitive deps (e.g. cryptography via ccxt) are Debian-managed there and
# pip refuses to upgrade them ("RECORD file not found").
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating virtualenv at $VENV..."
  python3 -m venv "$VENV"
fi

# Export the environment before the slow install rather than after, so the
# session picks up PATH/PYTHONPATH even while packages are still landing.
# These paths are known as soon as the venv exists.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    # Ahead of $PATH so bare `python`/`pytest`/`black` resolve to this env
    # instead of the system interpreter or isolated tool shims.
    echo "export PATH=\"$VENV/bin:\$PATH\""
    # Tests import `pwb_toolbox` from the repo root rather than an installed
    # distribution, and the package is not pip-installed here.
    echo "export PYTHONPATH=\"$PROJECT_DIR\${PYTHONPATH:+:\$PYTHONPATH}\""
  } >> "$CLAUDE_ENV_FILE"
fi

echo "Installing pwb-toolbox dependencies with $("$VENV/bin/python" --version)..."
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements-dev.txt
"$VENV/bin/python" -m pip install --quiet black

echo "Dependencies installed. Run tests with: pytest tests/ -v"
