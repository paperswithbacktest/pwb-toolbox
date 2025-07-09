from dataclasses import dataclass
from enum import Enum, auto
from datetime import datetime


class Direction(Enum):
    """Possible directions for an Insight."""

    UP = auto()
    DOWN = auto()
    FLAT = auto()


@dataclass
class Insight:
    """Simple trading signal produced by an Alpha model."""

    symbol: str
    direction: Direction
    timestamp: datetime
    weight: float = 1.0
