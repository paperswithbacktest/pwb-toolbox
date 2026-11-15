"""pwb_toolbox is now ``pwb`` (``pip install paperswithbacktest``).

This compatibility package keeps ``import pwb_toolbox`` and every
``pwb_toolbox.<module>`` working: each name resolves to the **same module
object** as its ``pwb`` counterpart (``pwb_toolbox.backtesting is
pwb.backtesting``), so classes, the engine chosen by ``pwb.engine`` and every
cache are shared, and nothing runs twice. Importing it warns once with a
``DeprecationWarning``; replace ``pwb_toolbox`` with ``pwb`` in the imports.
"""

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

_OLD = __name__  # "pwb_toolbox"
_NEW = "pwb"

warnings.warn(
    "pwb_toolbox has been renamed pwb (pip install paperswithbacktest): "
    "replace `pwb_toolbox` with `pwb` in your imports; this alias will be removed "
    "in a future release",
    DeprecationWarning,
    stacklevel=2,
)


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target):
        self.target = target

    def create_module(self, spec):
        # The pwb module itself: the import system then files it under the old name too.
        module = importlib.import_module(self.target)
        self.spec = module.__spec__
        return module

    def exec_module(self, module):
        # Already executed under its pwb name. The import system has just set
        # ``__spec__`` to the alias' spec (it always does): put pwb's back, so the
        # module keeps one identity (``__spec__.name == __name__``, reload, pickle).
        module.__spec__ = self.spec

    def get_code(self, fullname):
        # ``python -m pwb_toolbox.engine ...``: runpy asks for the code to run as __main__.
        spec = importlib.util.find_spec(self.target)
        return spec.loader.get_code(self.target)


class _AliasFinder(importlib.abc.MetaPathFinder):
    """``pwb_toolbox.x.y`` -> the module ``pwb.x.y``, imported once under its new name."""

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_OLD + "."):
            return None
        new = _NEW + fullname[len(_OLD):]
        if importlib.util.find_spec(new) is None:
            return None
        return importlib.util.spec_from_loader(fullname, _AliasLoader(new))


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

# ``import pwb_toolbox`` gives the pwb package itself, so ``pwb_toolbox.__version__``,
# ``pwb_toolbox.backtesting`` (once imported) and the rest are pwb's.
sys.modules[_OLD] = importlib.import_module(_NEW)
