"""Command line front end: ``python -m pwb_toolbox.scraping``."""

import click

from .polite import PoliteSession, RobotsDisallowed
from .sources.github import GitHubSource, SkippedRepository
from .sources.tradingview import TradingViewSource
from .store import ScriptStore


def _report(store: ScriptStore, added: int, warnings: list[str]) -> None:
    for warning in warnings:
        click.echo(f"warning: {warning}", err=True)
    click.echo(f"{added} new script(s); {len(store)} in {store.root}")


@click.group()
def cli():
    """Collect PineScript and thinkScript source into a local corpus."""


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--out", default="script-corpus", show_default=True)
@click.option("--ref", default=None, help="Branch, tag or commit. Defaults to HEAD.")
@click.option(
    "--allow-any-license",
    is_flag=True,
    help="Keep code from repositories without a permissive license.",
)
@click.option(
    "--include-commercial",
    is_flag=True,
    help="Keep files whose headers mark them as paid or non-redistributable.",
)
def github(repos, out, ref, allow_any_license, include_commercial):
    """Collect scripts from one or more OWNER/NAME repositories."""
    source = GitHubSource(
        require_license=not allow_any_license,
        skip_commercial=not include_commercial,
    )
    store = ScriptStore(out)
    added = 0
    for repo in repos:
        try:
            added += store.extend(source.collect(repo, ref=ref))
        except SkippedRepository as exc:
            click.echo(f"skipped: {exc}", err=True)
    _report(store, added, source.warnings)


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--out", default="script-corpus", show_default=True)
@click.option(
    "--accept-terms",
    is_flag=True,
    help="Acknowledge the terms described in sources/tradingview.py.",
)
def tradingview(urls, out, accept_terms):
    """Fetch individual published TradingView script pages."""
    source = TradingViewSource(
        session=PoliteSession(min_interval=5.0), accept_terms=accept_terms
    )
    store = ScriptStore(out)
    added, warnings = 0, []
    for url in urls:
        try:
            record = source.fetch(url)
        except RobotsDisallowed as exc:
            warnings.append(str(exc))
            continue
        if record is None:
            warnings.append(f"{url}: no open-source PineScript found on the page")
            continue
        added += int(store.add(record))
    _report(store, added, warnings)
