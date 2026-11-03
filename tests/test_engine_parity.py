"""The toolbox layer gives the same NAV path on both engines.

Not a test of the engines (Tradewind's own oracle harness does that): a test
that everything *this package* wires around a strategy -- ``BaseStrategy``'s
log, ``ArrayPandasData``, the per-symbol ``SpreadImpactCommission`` with a
yearly schedule, ``FundingAudit`` / ``FillAudit``, the listing guard and the
exposure cap -- behaves the same whichever engine ``pwb_toolbox.engine``
picked. Synthetic bars, no download, a few seconds.

Skipped unless both engines are importable by this interpreter.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

from pwb_toolbox import engine

SCRIPT = r"""
import json
import numpy as np
import pandas as pd
import pwb_toolbox.backtesting as pwb_bt
from pwb_toolbox.backtesting.backtest_engine import (
    FillAudit, FundingAudit, _refuse_before_listing, _with_exposure_cap,
)
from pwb_toolbox.backtesting.feeds import ArrayPandasData

bt = pwb_bt.bt
rng = np.random.default_rng(3)
index = pd.bdate_range("2019-01-02", periods=320)
frames = {}
for i in range(5):
    close = 40 * np.exp(np.cumsum(rng.normal(0.0003, 0.013, len(index))))
    openp = close * (1 + rng.normal(0, 0.003, len(index)))
    frames[f"S{i}"] = pd.DataFrame({
        "open": openp, "high": np.maximum(openp, close) * 1.004,
        "low": np.minimum(openp, close) * 0.996, "close": close, "volume": 1e5}, index=index)
# S4 lists 60 bars late: back-filled flat in front, as run_strategy does.
late = frames["S4"].copy()
late.iloc[:60] = late.iloc[60].values
frames["S4"] = late
first_bar = {"S4": index[60]}


class Monthly(pwb_bt.BaseStrategy):
    params = (("leverage", 1.4),)

    def __init__(self):
        super().__init__()
        self.sma = {d._name: bt.indicators.SMA(d.close, period=20) for d in self.datas}
        self.last = None

    def next(self):
        super().next()
        today = self.datas[0].datetime.date(0)
        if (today.year, today.month) == self.last:
            return
        self.last = (today.year, today.month)
        # ``>=`` so the flat prefix of S4 qualifies and the listing guard has orders
        # to refuse; a flat series is where the SMA's rounding showed between engines.
        longs = [d for d in self.datas if d.close[0] >= self.sma[d._name][0]]
        for d in self.datas:
            target = self.p.leverage / len(longs) if d in longs else 0.0
            self.order_target_percent(d, target=target)


cerebro = bt.Cerebro(stdstats=False)
feeds = {}
for name, frame in frames.items():
    data = ArrayPandasData(dataname=frame)
    cerebro.adddata(data, name=name)
    feeds[name] = data
cerebro.addstrategy(_with_exposure_cap(Monthly, 0.6), total_days=len(index))
cerebro.addanalyzer(FundingAudit, _name="funding")
cerebro.addanalyzer(FillAudit, _name="fill", inactive={"S4": {2019}})
cerebro.broker.set_cash(250_000)
for k, name in enumerate(frames):
    scheme = pwb_bt.SpreadImpactCommission(
        half_spread=0.0005 * (k + 1),
        schedule={2019: (0.0004 * (k + 1), 0.0), 2020: (0.0002 * (k + 1), 0.0)},
        data=feeds[name],
    )
    cerebro.broker.addcommissioninfo(scheme, name=name)
listing = _refuse_before_listing(cerebro.broker, first_bar)
strat = cerebro.run()[0]
print(json.dumps({
    "nav": [row["value"] for row in strat.log_data],
    "dates": [row["date"] for row in strat.log_data],
    "cash": cerebro.broker.getcash(),
    "positions": strat.get_latest_positions(),
    "funding": strat.analyzers.funding.get_analysis(),
    "fill": strat.analyzers.fill.get_analysis(),
    "listing": {k: v["orders"] for k, v in listing.items()},
    "requested_gross": strat.requested_gross,
}))
"""


def _run(engine_name):
    env = {**os.environ, engine.ENV_VAR: engine_name, "TQDM_DISABLE": "1"}
    proc = subprocess.run(
        [sys.executable, "-c", SCRIPT], env=env, capture_output=True, text=True, check=False
    )
    if proc.returncode:
        raise AssertionError(f"{engine_name}: {proc.stderr.strip().splitlines()[-1]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


@unittest.skipUnless(
    importlib.util.find_spec("backtrader") and importlib.util.find_spec("tradewind"),
    "both engines are needed",
)
class EngineParityTest(unittest.TestCase):
    def test_same_nav_audits_and_refusals_on_both_engines(self):
        ref, cand = _run("backtrader"), _run("tradewind")
        self.assertEqual(ref["dates"], cand["dates"])
        # 320 bars less the 19 the 20-bar SMA needs before ``next`` first runs.
        self.assertEqual(len(ref["nav"]), 301)
        worst = max(abs(a - b) for a, b in zip(ref["nav"], cand["nav"]))
        self.assertLess(worst, 1e-6, f"NAV paths differ by up to {worst}")
        self.assertAlmostEqual(ref["cash"], cand["cash"], places=6)
        self.assertEqual(ref["positions"], cand["positions"])
        for key in ("margin", "submitted", "reject_rate"):
            self.assertEqual(ref["funding"][key], cand["funding"][key], key)
        for key in ("min_cash", "min_value"):  # cash accumulates in a different order
            self.assertAlmostEqual(ref["funding"][key], cand["funding"][key], places=4, msg=key)
        self.assertEqual(ref["fill"], cand["fill"])
        self.assertEqual(ref["listing"], cand["listing"])
        self.assertAlmostEqual(ref["requested_gross"], cand["requested_gross"], places=9)
        self.assertGreater(ref["listing"].get("S4", 0), 0, "the listing guard never fired")
        self.assertGreater(ref["funding"]["submitted"], 0)


if __name__ == "__main__":
    unittest.main()
