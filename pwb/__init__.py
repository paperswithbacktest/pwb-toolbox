"""pwb: the Papers With Backtest library (``pip install paperswithbacktest``).

Formerly ``pwb_toolbox`` (``pip install pwb-toolbox``). The old name stays
importable through the ``pwb-toolbox`` compatibility release, which depends on
this package, gives the very same modules and warns once (``DeprecationWarning``).
"""

# The release this code is: what the harness checks report as ``toolboxVersion``.
# Kept equal to ``version`` in setup.cfg (tests/test_harness_checks.py checks it):
# the installed metadata can belong to another copy than the one imported.
__version__ = "0.2.0"
