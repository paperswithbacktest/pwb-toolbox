"""Reader of the PWB World Model: who an identifier was, and the graph, at a date.

The World Model is a set of private tables on the Hub -- ``WorldModel-Entities``,
``WorldModel-Identifiers`` and one ``WorldModel-Edges-<Family>`` per family of
relations -- that a strategy reads **as it was knowable at date T**:

* a row exists at T only if it was published by then (``known_at <= T``);
  a correction published later never changes what T sees;
* among those, each key keeps its latest publication, and the row whose
  half-open interval ``[valid_from, valid_to)`` holds the date is the answer.

>>> from pwb_toolbox import world_model as wm
>>> wm.resolve("TGX", "2012-06-01")                         # doctest: +SKIP
>>> wm.resolve_panel(["TGX", "GOOGL"], dates)               # doctest: +SKIP
>>> wm.get_graph("2020-12-31", relations=["customer_of"])   # doctest: +SKIP

See ``docs/world_model.md`` (``python -m pwb_toolbox.docs world_model``).
"""

from ._source import LOCAL_DIR_ENV, WorldModelNotAvailable
from .reader import RELATIONS, WorldModel, get_graph, resolve, resolve_panel

__all__ = [
    "LOCAL_DIR_ENV",
    "RELATIONS",
    "WorldModel",
    "WorldModelNotAvailable",
    "get_graph",
    "resolve",
    "resolve_panel",
]
