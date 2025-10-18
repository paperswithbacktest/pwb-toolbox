# PWB Fund

## Installation

Install:

```bash
export GITHUB_USERNAME=
export GITHUB_TOKEN=
bash install.sh
```

## Fix

```bash
# To restart the desktop environment:
ps aux | grep xfce4
sudo pkill -u ubuntu
```

## Usage

### Scripts

Run the live execution script to connect to Interactive Brokers and log the current account state:

```bash
PWB_API_KEY=8ea622baa9f3e1dafe00ff1375d5206c9ff7f896ca2699f7198d2850e25846c2  python -m src.execute
```

This creates an `$HOME/Documents/pwb-fund/strategies/ib/execution_logs/` directory
containing runtime artifacts:

```
$HOME/Documents/pwb-fund/strategies/ib/execution_logs/
└── 2024-06-09.json
```

Each `*.json` file captures NAV, positions, orders, executed trades, and NAV history for that run. Both the NAV series and trade statistics are derived from the aggregated `*.json` files.

Monitor and analyze a logs directory using:

```bash
python -m src.monitor --logs-dir $HOME/Documents/pwb-fund/strategies/ib/execution_logs
```

The command above generates plots under
`$HOME/Documents/pwb-fund/strategies/ib/execution_logs/plots` and saves NAV
metrics and trade statistics to
`$HOME/Documents/pwb-fund/strategies/ib/monitoring_reports`.

## Scheduled execution with Airflow

Airflow

```bash
cd ~/pwb-fund
conda activate pwb-fund
AIRFLOW_HOME="airflow" airflow standalone
```

In the console output immediately after startup, you’ll see a line like:

```bash
standalone | Airflow is ready
standalone | Login with username: admin  password: XyZ123AbCd
```

A DAG (`dags/ib_execute_dag.py`) runs the live execution script every business day.


