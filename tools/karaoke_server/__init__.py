"""A shared leaderboard for static/karaoke-box.html.

Run it with `python -m tools.karaoke_server`; see README.md in this
directory. Unrelated to the trading library -- it exists only to give the
karaoke page somewhere to post scores.
"""

from .board import Board, ValidationError, clean_entry

__all__ = ["Board", "ValidationError", "clean_entry"]
