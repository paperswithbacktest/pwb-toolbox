#!/bin/bash
# tb1122_run.sh <label new|base> <key> <strategy rel path>   -- e2e of pwb-toolbox fixes 22 Nov 2026 (two at a time)
set -u
R=/home/ubuntu/remeasure; N=$R/harness/tb1122
unset PWB_API_KEY PYTHONPATH PWB_BACKTEST_ENGINE PWB_HF_OFFLINE HF_HUB_OFFLINE NC_VARIANT
HF_ACCESS_TOKEN="$(cd /home/ubuntu/api && docker compose exec -T airflow-worker printenv HF_ACCESS_TOKEN 2>/dev/null)"
export HF_ACCESS_TOKEN HF_HOME=$R/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_PINS_FILE=$R/harness/rm0153/hf_pins_20261118.json
TREE=$R/papers-5021207
[ "$1" = new ] && export PYTHONPATH=$N/src
export PAPERS_DIR=$TREE NAV_DIR=$N/out/nav_$1 NC_KEY=$2
cd $TREE && $R/venv0153/bin/python -c "import pwb_toolbox;print('TOOLBOX', pwb_toolbox.__file__)" > $N/out/$1_$2.log 2>&1
cd $TREE && timeout 7200 nice -n 10 $R/venv0153/bin/python -u $R/harness/rm0153/remeasure_measure.py "$3" >> $N/out/$1_$2.log 2>&1
echo "$(date -u +%FT%TZ) $1 $2 exit $?" >> $N/out/_done.txt
