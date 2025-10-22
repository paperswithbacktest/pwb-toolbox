#!/usr/bin/env bash
set -euo pipefail

# 1. Ensure conda is usable in non-interactive script
# (adjust path if your Miniconda/Anaconda is installed elsewhere)
source "${HOME}/miniconda3/etc/profile.d/conda.sh"

# 2. Activate the environment
ENV_NAME="pwd"
conda activate "${ENV_NAME}"

# 3. Run the sequence of Python modules
echo "Running launch_ib..."
python -m launch_ib

echo "launch_ib succeeded ⇒ running execute_meta_strategy..."
python -m execute_meta_strategy

echo "Done."