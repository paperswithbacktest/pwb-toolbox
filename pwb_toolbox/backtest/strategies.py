import backtrader as bt
import numpy as np
from .base_strategy import BaseStrategy


class DailyEqualWeightPortfolio(BaseStrategy):
    """
    Generic portfolio that:
    • Opens long positions in assets whose Signal == 1;
    • Allocates equal weight (leverage / n_long);
    • Re‑evaluates (and therefore rebalances) **every trading day**.
    """

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }

    def next(self):
        super().next()

        # Which assets still qualify?
        longs = [d for d in self.datas if self.sig[d._name][0] == 1]
        n = len(longs)
        target_wt = (self.p.leverage / n) if n else 0.0

        # Size / resize positions
        for d in self.datas:
            self.order_target_percent(d, target=target_wt if d in longs else 0.0)


class DailyLeveragePortfolio(BaseStrategy):
    """
    Generic: go `leverage` long whenever signal == 1, otherwise flat.
    """

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        # One signal instance per data stream
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }
        # Match legacy behaviour – fill at today's close
        self.broker.set_coc(True)

    def next(self):
        super().next()  # keeps log/value tracking from BaseStrategy
        for d in self.datas:
            tgt = self.p.leverage if self.sig[d._name][0] == 1 else 0.0
            self.order_target_percent(d, target=tgt)


class EqualWeightEntryExitPortfolio(BaseStrategy):
    """
    Opens new longs equally‑weighted across *all* instruments that are in
    `entry == 1` state on the current bar.
    Existing positions are not resized; this mirrors the behaviour of the
    original script and therefore preserves Sharpe, draw‑down, etc.
    """

    params = dict(
        leverage=0.90,
        indicator_cls=None,  # will be injected by run_strategy
        indicator_kwargs={},
    )

    def __init__(self):
        super().__init__()
        # One signal instance per data feed
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }

    def next(self):
        super().next()  # keeps BaseStrategy bookkeeping intact

        # Instruments that satisfy the breakout condition *today*
        todays_trending = [
            d
            for d in self.datas
            if self.sig[d._name].entry[0] == 1 and self.is_tradable(d)
        ]

        n_trending = len(todays_trending)
        tgt_weight = (self.p.leverage / n_trending) if n_trending else 0.0

        for d in self.datas:
            pos_size = self.getposition(d).size
            sig = self.sig[d._name]

            # Exit—immediately flat if the stop is hit
            if sig.exit[0] == 1 and pos_size > 0:
                self.order_target_percent(d, target=0.0)

            # Entry—open only if flat; weight is based on the current
            # number of *breakout* instruments, matching the original logic
            elif sig.entry[0] == 1 and pos_size == 0:
                self.order_target_percent(d, target=tgt_weight)


class DynamicEqualWeightPortfolio(BaseStrategy):
    """
    Generic event‑driven equal‑weight, long‑only portfolio.

    • Reads per‑asset binary signals (1 = long, 0/−1 = flat).
    • Re‑allocates when either
        – the *set* of long assets changes          (default); or
        – *any* individual signal flips 0↔1/-1      (`trigger_on_any_change=True`).

    Parameters
    ----------
    leverage : float      – gross notional exposure (default 0.9)
    trigger_on_any_change : bool
        False → rebalance only when the **set** of longs changes
        True  → rebalance whenever *any* asset's signal changes
    indicator_cls : type     – class that yields the signal (must indexable)
    indicator_kwargs : dict  – forwarded to `indicator_cls`
    """

    params = dict(
        leverage=0.9,
        trigger_on_any_change=False,
        indicator_cls=None,
        indicator_kwargs={},
    )

    # ------------------------------------------------------------------ #
    def __init__(self):
        super().__init__()
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }
        self._prev_longs: set[str] = set()
        self._prev_raw: dict[str, int | None] = {d._name: None for d in self.datas}

    # ------------------------------------------------------------------ #
    def _compute_current_longs(self) -> set[str]:
        return {
            d._name
            for d in self.datas
            if self.is_tradable(d) and int(self.sig[d._name][0]) == 1
        }

    # ------------------------------------------------------------------ #
    def _any_signal_changed(self) -> bool:
        changed = False
        for d in self.datas:
            cur = int(self.sig[d._name][0])
            if self._prev_raw[d._name] is None or cur != self._prev_raw[d._name]:
                changed = True
            self._prev_raw[d._name] = cur
        return changed

    # ------------------------------------------------------------------ #
    def next(self):
        super().next()

        # ----- Decide whether we need to rebalance ----------------------
        longs_now = self._compute_current_longs()

        if self.p.trigger_on_any_change:
            rebalance = self._any_signal_changed()
        else:
            rebalance = longs_now != self._prev_longs

        if not rebalance:
            return

        # ----- Re‑allocate ---------------------------------------------
        wt = (self.p.leverage / len(longs_now)) if longs_now else 0.0
        for d in self.datas:
            self.order_target_percent(d, target=wt if d._name in longs_now else 0.0)

        self._prev_longs = longs_now


class MonthlyLongShortPortfolio(BaseStrategy):
    """
    A minimal monthly rebalancing wrapper that understands any signal
    object exposing `.compute()` → (longs, shorts).

    Weighting rule:
        – ½ × leverage equally across longs
        – ½ × leverage equally across shorts (negative weights)
    """

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        # Instantiate the universe‑aware signal
        self.sig = self.p.indicator_cls(self.datas, **self.p.indicator_kwargs)
        self._last_month = -1

    # ------------------------------------------------------------------
    def next(self):
        super().next()

        today = self.datas[0].datetime.date(0)
        if today.month == self._last_month:
            return  # already processed this calendar month
        self._last_month = today.month

        decision = self.sig.compute()
        if decision is None:
            return  # keep existing positions unchanged

        longs, shorts = decision
        n_long, n_short = len(longs), len(shorts)

        # Compute equal weights (handle zero‑division safely)
        w_long = (self.p.leverage / 2.0) / n_long if n_long else 0.0
        w_short = -(self.p.leverage / 2.0) / n_short if n_short else 0.0

        desired = set()

        # --- Allocate longs -------------------------------------------------
        for d in longs:
            desired.add(d._name)
            self.order_target_percent(d, target=w_long)

        # --- Allocate shorts ------------------------------------------------
        for d in shorts:
            desired.add(d._name)
            self.order_target_percent(d, target=w_short)

        # --- Close anything no longer desired ------------------------------
        for d in self.datas:
            if d._name not in desired:
                self.order_target_percent(d, target=0.0)


class MonthlyLongShortQuantilePortfolio(BaseStrategy):
    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        # One signal per asset – all share the same universe
        self.sig = {
            d._name: self.p.indicator_cls(
                d,
                universe=self.datas,
                **self.p.indicator_kwargs,
            )
            for d in self.datas
        }

        # Fire on first trading day of every month
        self.add_timer(
            when=bt.Timer.SESSION_START,
            monthdays=[1],
            monthcarry=True,
        )

    def next(self):
        super().next()  # keep BaseStrategy bookkeeping

    # -------------------------- monthly rebalance ------------------------------
    def notify_timer(self, timer, when, *args, **kwargs):
        self.rebalance()

    def rebalance(self):
        longs = [
            d for d in self.datas if self.sig[d._name][0] == 1 and self.is_tradable(d)
        ]
        shorts = [
            d for d in self.datas if self.sig[d._name][0] == -1 and self.is_tradable(d)
        ]
        n = len(longs) + len(shorts)

        # If nothing qualifies, go flat
        if n == 0:
            for d in self.datas:
                self.order_target_percent(d, target=0.0)
            return

        wt = self.p.leverage / n  # equal weight (gross exposure = leverage)

        for d in self.datas:
            sig = self.sig[d._name][0]
            if sig == 1:
                self.order_target_percent(d, target=wt)
            elif sig == -1:
                self.order_target_percent(d, target=-wt)
            else:
                self.order_target_percent(d, target=0.0)


class MonthlyRankedEqualWeightPortfolio(BaseStrategy):
    """
    Generic once‑per‑month equal‑weight portfolio with optional ranking.

    Workflow
    --------
    1. On the first trading day of each calendar month:
       • Build the candidate list:
           – If *num_selection* is None/0 → all assets whose signal == 1.
           – Else                          → rank assets by a chosen score
                                             and keep the top *num_selection*.
       • Optionally filter out non‑positive signals (`filter_nonpositive`).
    2. Exit losers immediately.
    3. If *reweight_existing* is True, size **all** winners to
       `leverage / num_selection` (or / n_active if num_selection is None).
       Otherwise, size only *new* winners; existing positions drift.

    Parameters
    ----------
    leverage : float
    num_selection : int | None
        None or 0   → “invest in **all** qualifying assets”
        integer > 0 → keep the top N assets after ranking
    reweight_existing : bool
    filter_nonpositive : bool
        Ignore assets whose score / signal <= 0 when ranking.
    rank_attr : {'value', 'score'}
        'value' → use `signal[0]`
        'score' → use `signal.score[0]`  (as in MonthlyTopNEqualWeightPortfolio)
    indicator_cls , indicator_kwargs : see BaseStrategy
    """

    params = dict(
        leverage=0.9,
        num_selection=None,
        reweight_existing=True,
        filter_nonpositive=False,
        rank_attr="value",  # 'value' or 'score'
        indicator_cls=None,
        indicator_kwargs={},
    )

    # ------------------------------------------------------------------ #
    def __init__(self):
        super().__init__()
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }
        self._last_month = -1

    # ------------------------------------------------------------------ #
    def _score(self, d) -> float:
        if self.p.rank_attr == "score":
            return float(self.sig[d._name].score[0])
        return float(self.sig[d._name][0])

    # ------------------------------------------------------------------ #
    def next(self):
        super().next()
        today = self.datas[0].datetime.date(0)
        if today.month == self._last_month:
            return
        self._last_month = today.month

        # ----- Build candidate list ------------------------------------
        if not self.p.num_selection:
            # “all assets with signal == 1”
            keep = [
                d
                for d in self.datas
                if self.is_tradable(d) and int(self.sig[d._name][0]) == 1
            ]
        else:
            ranked = []
            for d in self.datas:
                if not self.is_tradable(d):
                    continue
                s = self._score(d)
                if self.p.filter_nonpositive and s <= 0:
                    s = -float("inf")
                ranked.append((d, s))

            ranked.sort(key=lambda tup: tup[1], reverse=True)
            keep = [d for d, _ in ranked[: self.p.num_selection]]

        # ----- Exit losers ---------------------------------------------
        for d in self.datas:
            if d not in keep and self.getposition(d).size != 0:
                self.order_target_percent(d, target=0.0)

        # ----- Enter / resize winners ----------------------------------
        n_keep = len(keep)
        tgt = (self.p.leverage / n_keep) if n_keep else 0.0

        for d in keep:
            already_long = self.getposition(d).size != 0
            if already_long and not self.p.reweight_existing:
                continue  # leave position unchanged
            self.order_target_percent(d, target=tgt)


class QuarterlyTopMomentumPortfolio(BaseStrategy):
    params = (
        ("leverage", 0.90),
        ("indicator_cls", None),  # will be Momentum90dSignal
        ("indicator_kwargs", {}),  # {"lookback": 90}
    )

    def __init__(self):
        super().__init__()

        # Attach one signal per data feed
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }

        self._last_rebalance_ym: tuple[int, int] | None = None
        self._current_winner: str | None = None  # symbol we are presently long

    # ---------------------------------------------------------------------
    # Core trading loop
    # ---------------------------------------------------------------------
    def next(self):
        super().next()  # keeps logs/metrics from BaseStrategy

        today = self.datas[0].datetime.date(0)

        # Rebalance only on the FIRST trading day of Jan/Apr/Jul/Oct
        if today.month % 3 != 0:
            return
        year_month = (today.year, today.month)
        if year_month == self._last_rebalance_ym:  # already rebalanced this month
            return
        self._last_rebalance_ym = year_month

        # -----------------------------------------------------------------
        # 1️⃣  Find the asset with the highest 90‑day perf
        # -----------------------------------------------------------------
        best_asset, best_perf = None, float("-inf")
        tie = False

        for d in self.datas:
            if not self.is_tradable(d):
                continue
            perf = self.sig[d._name][0]
            if perf > best_perf:
                best_asset, best_perf, tie = d, perf, False
            elif perf == best_perf:
                tie = True

        # -----------------------------------------------------------------
        # 2️⃣  Decide the target allocation
        #     • Unique winner  →  90 % into that asset
        #     • Tie / no data →  100 % cash
        # -----------------------------------------------------------------
        if tie or best_asset is None:
            new_winner = None
        else:
            new_winner = best_asset._name

        # If nothing changed, hold current positions unchanged
        if new_winner == self._current_winner:
            return

        self._current_winner = new_winner

        for d in self.datas:
            if d._name == new_winner:
                self.order_target_percent(d, target=self.p.leverage)
            else:
                self.order_target_percent(d, target=0.0)


class RollingSemesterLongShortPortfolio(BaseStrategy):
    """Semi-annual rebalancing portfolio that:
    • rebalances at the start of each semester
    • invests in long and short positions based on signals
    • uses leverage to achieve the target exposure
    """

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),  # <-- will be supplied when strategy is added
        ("indicator_kwargs", {}),  # <-- additional parameters for the signal
    )

    def __init__(self):
        super().__init__()
        assert self.p.indicator_cls is not None, "indicator_cls must be provided"
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }
        self.hist = {d._name: [0] * 6 for d in self.datas}
        self.add_timer(when=bt.Timer.SESSION_START, monthdays=[1], monthcarry=True)

    # ---------------------------------------------------------------------#
    def notify_timer(self, *_, **__):
        today = self.datas[0].datetime.date(0)
        slot = (today.month - 1) // 6  # 0 = Jan-Jun, 1 = Jul-Dec

        longs, shorts = [], []
        for d in self.datas:
            raw = self.sig[d._name][0]
            flag = 0 if np.isnan(raw) else int(round(raw))
            self.hist[d._name][slot] = flag
            if flag == 1:
                longs.append(d)
            elif flag == -1:
                shorts.append(d)

        active = len(longs) + len(shorts)
        if active == 0:
            return

        for d in self.datas:
            avg = np.sum(self.hist[d._name]) / 6.0
            target = avg / active * self.p.leverage
            self.order_target_percent(d, target=target)

    def next(self):
        super().next()


class WeeklyLongShortDecilePortfolio(BaseStrategy):
    """
    Generic long/short portfolio that:
      • rebalances weekly (default Monday)               – param rebalance_weekday
      • goes long bottom X% and short top X% of signals  – param decile_fraction
      • splits <leverage> equally across all active legs – param leverage
    """

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),  # e.g. ROC5Signal
        ("indicator_kwargs", {}),  # extra args for the signal
        ("rebalance_weekday", 0),  # 0 = Monday
        ("decile_fraction", 0.10),  # 10 % ⇒ classic “decile” rule
    )

    def __init__(self):
        super().__init__()

        # Attach one signal instance per data feed
        self.sig = {
            d._name: self.p.indicator_cls(d, **self.p.indicator_kwargs)
            for d in self.datas
        }

        # Ensure Close‑on‑Close execution so fills match the original back‑test
        self.broker.set_coc(True)

        self._last_rebalance_date = None

    # --------------------------------------------------------------------- #
    #  Generic weekly re‑balance                                            #
    # --------------------------------------------------------------------- #
    def next(self):
        super().next()

        today = self.datas[0].datetime.date(0)
        if today.weekday() != self.p.rebalance_weekday:
            return
        if self._last_rebalance_date == today:
            return  # already rebalanced this bar

        self._rebalance_portfolio()
        self._last_rebalance_date = today

    # --------------------------------------------------------------------- #
    #  Rebalance helper                                                     #
    # --------------------------------------------------------------------- #
    def _rebalance_portfolio(self):
        # Collect (data, signal‑value) pairs for tradable assets
        signals = [
            (d, float(self.sig[d._name][0]))
            for d in self.datas
            if self.is_tradable(d) and len(self.sig[d._name]) > 0
        ]

        n_assets = len(signals)
        if n_assets < 10:
            # Same rule as the original: flat book if insufficient universe
            for d in self.datas:
                self.order_target_percent(d, 0.0)
            return

        # Sort by signal descending (highest momentum first)
        signals.sort(key=lambda x: x[1], reverse=True)

        # Determine decile size (min 1 to mimic int(len/10) logic)
        decile_size = max(1, int(n_assets * self.p.decile_fraction))

        short_list = [d for d, _ in signals[:decile_size]]
        long_list = [d for d, _ in signals[-decile_size:]]
        n_positions = len(long_list) + len(short_list)

        if n_positions == 0:
            return  # nothing to do

        weight = self.p.leverage / n_positions

        # Deploy targets
        for d in self.datas:
            if d in long_list:
                self.order_target_percent(d, weight)
            elif d in short_list:
                self.order_target_percent(d, -weight)
            else:
                self.order_target_percent(d, 0.0)


class WeightedAllocationPortfolio(BaseStrategy):
    """A light wrapper that turns the weights emitted by *any* signal into
    integer share positions under a given leverage constraint."""

    params = (
        ("leverage", 0.9),
        ("indicator_cls", None),
        ("indicator_kwargs", {}),
    )

    def __init__(self):
        super().__init__()
        # Single signal instance that sees *all* data feeds.
        self.sig = self.p.indicator_cls(*self.datas, **self.p.indicator_kwargs)
        self.last_month = -1

    def next(self):
        super().next()

        # Rebalance once per month (same cadence as the signal).
        today = self.datas[0].datetime.date(0)
        if today.month == self.last_month:
            return
        self.last_month = today.month

        weights = self.sig.get_weights()
        total_value = self.broker.getvalue()

        for d in self.datas:
            if not self.is_tradable(d):
                continue
            w = weights.get(d._name, 0.0)
            cash = total_value * w * self.p.leverage
            size = int(cash / d.close[0])  # integer shares exactly as before
            self.order_target_size(d, size)
