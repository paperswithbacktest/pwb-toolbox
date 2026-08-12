#!/usr/bin/env bash
# Daily re-merge of the local Grok chat export.
#
# Runs on your own machine, where the export actually lives. Install with:
#
#   crontab -e
#   7 8 * * *  /path/to/pwb-toolbox/tools/grok_export/run_daily.sh
#
# Quiet unless something changed, so it is safe to leave in cron: a run that
# finds no new grouping writes nothing and logs a single line.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXPORT_DIR="${GROK_EXPORT_DIR:-${REPO_ROOT}/grok-export}"
LOG="${EXPORT_DIR}/merge.log"

cd "${REPO_ROOT}"

# Prefer the repo venv, fall back to whatever python is on PATH.
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ ! -d "${EXPORT_DIR}/raw" ]]; then
    echo "$(date -Is)  no export at ${EXPORT_DIR}/raw; nothing to do."
    exit 0
fi

mkdir -p "${EXPORT_DIR}"

# Fold in any new xAI download sitting next to the export before merging.
shopt -s nullglob
for archive in "${EXPORT_DIR}"/../*.zip "${HOME}"/Downloads/*xai*.zip; do
    if unzip -l "${archive}" 2>/dev/null | grep -q "prod-grok-backend.json"; then
        echo "$(date -Is)  folding in ${archive}"
        "${PYTHON}" -m tools.grok_export convert "${archive}" --out "${EXPORT_DIR}"
    fi
done
shopt -u nullglob

# Guarded: `ls` on a missing directory is a non-zero exit, which under
# `set -e` with `pipefail` would kill the script before it logged anything.
count_merged() {
    if [[ -d "${EXPORT_DIR}/merged" ]]; then
        find "${EXPORT_DIR}/merged" -maxdepth 1 -name '*.md' | wc -l | tr -d ' '
    else
        echo 0
    fi
}

BEFORE="$(count_merged)"
REPORT="$("${PYTHON}" -m tools.grok_export merge --out "${EXPORT_DIR}" 2>&1)"
AFTER="$(count_merged)"

{
    echo "$(date -Is)  ${BEFORE} -> ${AFTER} merged documents"
    if [[ "${BEFORE}" != "${AFTER}" ]]; then
        echo "${REPORT}"
    fi
} | tee -a "${LOG}"
