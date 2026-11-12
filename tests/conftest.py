"""Shared test set-up: nothing reaches the Hub.

The harness checks classify a bare ticker from the routes ``get_pricing``
reports, and fall back to the catalogue index for a name it did not report --
which is every name in a test, since the loader is replaced. An empty index
keeps that fallback offline; a test that needs one sets
``checks._INDEX_ROUTES`` itself.
"""

import pwb_toolbox.backtesting.checks as _checks

_checks._INDEX_ROUTES = {}
