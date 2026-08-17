"""Convert PineScript strategies into Backtrader ones.

This handles the shape a typical published strategy takes -- a declaration,
inputs, ``ta.*`` indicators, conditions and order calls -- and reports anything
else instead of guessing at it. See
:mod:`pwb_toolbox.converting.backtrader` for what is and is not translated.
"""

from .backtrader import (
    CROSSES,
    INDICATORS,
    ConversionError,
    ConversionResult,
    convert,
)
from .parser import PineSyntaxError, parse, tokenize

__all__ = [
    "CROSSES",
    "INDICATORS",
    "ConversionError",
    "ConversionResult",
    "PineSyntaxError",
    "convert",
    "parse",
    "tokenize",
]
