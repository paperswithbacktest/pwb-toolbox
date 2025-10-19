# Interactive Broker Server

## Installation

On a ubuntu server (for instance from https://www.ovhcloud.com/), install [Miniconda](https://www.anaconda.com/), [IB TWS](https://www.interactivebrokers.com/), and RDP with:

```bash
cd pwb-toolbox/tools/ib_server
./install.sh
conda activate pwb
```

If TWS is already started:

```bash
python -m execute_meta_strategy
```

If TWS isn'y already started:

```bash
python -m launch_tws && python -m execute_meta_strategy
```

And to run the startegy daily:

```bash
30 9 * * Mon-Fri /bin/bash /path/to/run_daily.sh >> /path/to/logfile 2>&1
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
PWB_API_KEY=  python -m src.execute
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

