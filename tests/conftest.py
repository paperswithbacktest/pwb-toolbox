"""Shared test set-up: nothing reaches the Hub.

The harness checks classify a bare ticker from the routes ``get_pricing``
reports, and fall back to the catalogue index for a name it did not report --
which is every name in a test, since the loader is replaced. An empty index
keeps that fallback offline; a test that needs one sets
``checks._INDEX_ROUTES`` itself.
"""

import pwb_toolbox.backtesting.checks as _checks

_checks._INDEX_ROUTES = {}

# The subscriber API's disk cache: never the user's own cache directory, and no
# Hub metadata request unless a test patches ``_api_file_index`` itself.
import atexit as _atexit
import os as _os
import shutil as _shutil
import tempfile as _tempfile

_API_CACHE_TMP = _tempfile.mkdtemp(prefix="pwb-test-cache-")
_atexit.register(_shutil.rmtree, _API_CACHE_TMP, True)
_os.environ["PWB_CACHE_DIR"] = _API_CACHE_TMP
_os.environ["PWB_API_HUB_INDEX"] = "0"
