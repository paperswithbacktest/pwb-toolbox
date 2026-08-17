"""Generate a daily market-close broadcast script for a text-to-speech avatar.

An operational script rather than part of the shipped ``pwb_toolbox`` package —
same footing as ``tools/ib_server`` and ``tools/grok_export``. It reads a
session out of ``pwb_toolbox.datasets``, reduces it to facts, and renders a
broadcast script with Eleven v3 audio tags and every number already spelled the
way it should be spoken. See ``README.md`` in this directory.
"""

from .market import MarketFacts, Quote, collect, demo_facts
from .script import ScriptOptions, preview, render, split_segments

__all__ = [
    "MarketFacts",
    "Quote",
    "ScriptOptions",
    "collect",
    "demo_facts",
    "preview",
    "render",
    "split_segments",
]
