"""The package's documentation pages, shipped in the wheel.

A sandbox that installed ``pwb-toolbox`` from PyPI (the site's research chat,
a server task) has no checkout of the repository: ``python -m pwb_toolbox.docs
backtesting`` prints ``docs/backtesting.md`` from the installed package. The
copies here are kept identical to ``docs/`` by ``tests/test_docs_shipped.py``.
"""

from importlib import resources

__all__ = ["pages", "read"]


def pages() -> list[str]:
    """The names of the pages shipped, without ``.md``."""
    return sorted(
        entry.name[:-3]
        for entry in resources.files(__name__).iterdir()
        if entry.name.endswith(".md")
    )


def read(name: str = "backtesting") -> str:
    """The Markdown text of one page (``"backtesting"``)."""
    name = name[:-3] if name.endswith(".md") else name
    if name not in pages():
        raise KeyError(f"no page {name!r}; shipped: {', '.join(pages())}")
    return resources.files(__name__).joinpath(f"{name}.md").read_text(encoding="utf-8")
