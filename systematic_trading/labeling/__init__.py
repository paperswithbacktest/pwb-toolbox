"""
Labeling techniques used in financial machine learning.
"""

from systematic_trading.labeling.labeling import (
    add_vertical_barrier,
    apply_pt_sl_on_t1,
    barrier_touched,
    drop_labels,
    get_bins,
    get_events,
)
from systematic_trading.labeling.trend_scanning import trend_scanning_labels
from systematic_trading.labeling.tail_sets import TailSetLabels
from systematic_trading.labeling.fixed_time_horizon import fixed_time_horizon
from systematic_trading.labeling.matrix_flags import MatrixFlagLabels
from systematic_trading.labeling.excess_over_median import excess_over_median
from systematic_trading.labeling.raw_return import raw_return
from systematic_trading.labeling.return_vs_benchmark import return_over_benchmark
from systematic_trading.labeling.excess_over_mean import excess_over_mean
