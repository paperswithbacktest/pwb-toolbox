"""Sphinx configuration for the pwb-toolbox documentation."""

import configparser
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_cfg = configparser.ConfigParser()
_cfg.read(ROOT / "setup.cfg")

project = "pwb-toolbox"
author = "Papers With Backtest"
copyright = f"{date.today().year}, {author}"
release = _cfg.get("metadata", "version", fallback="0.0.0")
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = []
html_title = f"pwb-toolbox {release}"
