from pathlib import Path

import pwb_toolbox.performance as pwb_perf


logs_dir = Path.home() / "pwb-fund-data" / "strategies" / "all" / "execution_logs"

reports_dir = logs_dir.parent / "monitoring_reports"

result = pwb_perf.generate_monitoring_report(logs_dir, reports_dir)

nav = result["nav_metrics"]
trades = result["trade_stats"]
paths = result["paths"]

print("NAV Metrics:")
print(f"  Total Return:          {nav.get('total_return', 0):.2%}")
print(f"  CAGR:                  {nav.get('cagr', 0):.2%}")
print(f"  Annualized Volatility: {nav.get('ann_vol', 0):.2%}")
print(f"  Max Drawdown:          {nav.get('max_dd', 0):.2%}")
print(f"  Sharpe Ratio:          {nav.get('sharpe', 0):.2f}")

print("\nTrade Statistics:")
print(f"  Hit Rate:              {trades.get('hit_rate', 0):.2%}")
print(
    f"  Avg Win/Loss:          {trades.get('avg_win', 0):.4f}/{trades.get('avg_loss', 0):.4f}"
)
print(f"  Expectancy:            {trades.get('expectancy', 0):.4f}")
print(f"  Profit Factor:         {trades.get('profit_factor', 0):.2f}")
print(f"  Turnover:              {trades.get('turnover_per_day', 0):.2f}/day")
print(f"  Entry Slippage:        {trades.get('entry_slippage', 0):.4f}")
print(f"  Exit Slippage:         {trades.get('exit_slippage', 0):.4f}")
print(f"  Avg Latency (s):       {trades.get('avg_latency_sec', 0):.2f}")
print(f"  Max Latency (s):       {trades.get('max_latency_sec', 0):.2f}")

print("\nArtifacts:")
print(f"  Report:                {paths['report_txt']}")
print(f"  Equity Curve:          {paths['equity_curve_png']}")
print(f"  Return Heatmap:        {paths['return_heatmap_png']}")
print(f"  Underwater:            {paths['underwater_png']}")
