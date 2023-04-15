"""
Utility functions. In particular Chapter20 code on Multiprocessing and Vectorization
"""

from systematic_trading.util.fast_ewma import ewma
from systematic_trading.util.multiprocess import (
    expand_call,
    lin_parts,
    mp_pandas_obj,
    nested_parts,
    process_jobs,
    process_jobs_,
    report_progress,
)
from systematic_trading.util.volatility import (
    get_daily_vol,
    get_garman_class_vol,
    get_yang_zhang_vol,
    get_parksinson_vol,
)
from systematic_trading.util.volume_classifier import get_bvc_buy_volume
from systematic_trading.util.generate_dataset import get_classification_data
