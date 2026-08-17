"""Command line interface for the Grok chat exporter.

Four subcommands, in the order you are likely to need them:

``probe``    one listing page, printed raw, to confirm the endpoint still works
``pull``     crawl every conversation from a signed-in session
``convert``  turn an official xAI data download into the same layout
``render``   rebuild Markdown from an earlier ``pull``, without the network
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import client as client_module
from . import merge, official, render, schema
from .auth import AuthError, load_cookie, missing_cookies
from .client import GrokClient, GrokError
from .schema import Conversation

DEFAULT_OUT = Path("grok-export")


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _build_client(args: argparse.Namespace) -> GrokClient:
    cookie = load_cookie(args.cookie)
    absent = missing_cookies(cookie)
    if absent:
        _log(
            f"warning: session cookies {', '.join(absent)} are missing; "
            "grok.com will probably reject this. Re-copy from a signed-in tab."
        )
    return GrokClient(
        cookie,
        base_url=args.base_url,
        delay=args.delay,
        list_paths=args.list_path or client_module.LIST_PATHS,
        detail_paths=args.detail_path or client_module.DETAIL_PATHS,
    )


def _write_outputs(
    out: Path, conversations: Sequence[Conversation], markdown: bool
) -> None:
    """Write the index and, unless suppressed, one Markdown file per chat."""
    if markdown:
        markdown_dir = out / "markdown"
        for conversation in conversations:
            render.write_markdown(markdown_dir, conversation)
    render.write_index(out, conversations)


def _load_raw(path: Path) -> Conversation | None:
    """Re-parse one archived payload from a previous run."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _log(f"warning: could not read {path.name}: {error}")
        return None
    if not isinstance(payload, dict):
        return None
    if "listing" not in payload and "detail" not in payload:
        # An archive written before the envelope was consistent, or by hand:
        # the file is the conversation entry itself.
        return schema.parse_conversation(payload)
    return schema.parse_conversation(payload.get("listing"), payload.get("detail"))


def cmd_probe(args: argparse.Namespace) -> int:
    grok = _build_client(args)
    page = grok.list_page(page_size=args.page_size)
    entries = list(schema.iter_conversation_payloads(page))

    _log(f"Endpoint answered. {len(entries)} conversation(s) on the first page.")
    if entries:
        parsed = schema.parse_conversation(entries[0])
        _log(f"First entry parsed as: id={parsed.id!r} title={parsed.title!r}")
        if not parsed.id:
            _log(
                "warning: no id field recognised. Check the JSON below and add the "
                "real key to ID_KEYS in schema.py."
            )
    json.dump(page, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    grok = _build_client(args)
    out: Path = args.out
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    conversations: list[Conversation] = []
    fetched = skipped = failed = 0

    try:
        for entry in grok.list_conversations(
            page_size=args.page_size, limit=args.limit
        ):
            conversation_id = str(schema.pick(entry, schema.ID_KEYS, "") or "")
            if not conversation_id:
                _log("warning: listing entry has no id; skipping.")
                failed += 1
                continue

            archive = render.raw_path(raw_dir, conversation_id)
            if archive.exists() and not args.refresh:
                cached = _load_raw(archive)
                if cached is not None:
                    conversations.append(cached)
                    skipped += 1
                    continue

            detail = None
            try:
                detail = grok.fetch_detail(conversation_id)
            except GrokError as error:
                # Keep the listing metadata: a failed turn fetch loses the body,
                # not the record that the conversation exists.
                _log(f"warning: {conversation_id}: {error}")
                failed += 1

            render.write_raw(
                raw_dir, conversation_id, {"listing": entry, "detail": detail}
            )
            conversation = schema.parse_conversation(entry, detail)
            conversations.append(conversation)
            fetched += 1
            _log(
                f"[{fetched}] {conversation.display_title} ({len(conversation.messages)} msgs)"
            )
    except KeyboardInterrupt:
        _log("\nInterrupted; writing what has been collected so far.")
    except (AuthError, GrokError) as error:
        _log(f"error: {error}")
        if conversations:
            _write_outputs(out, conversations, not args.no_markdown)
            _log(f"Partial export written to {out}/")
        return 1

    _write_outputs(out, conversations, not args.no_markdown)
    _log(
        f"\n{len(conversations)} conversation(s) in {out}/ "
        f"({fetched} fetched, {skipped} already cached, {failed} failed)."
    )
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    source: Path = args.source
    if not source.exists():
        _log(f"error: {source} does not exist.")
        return 1

    conversations = official.load_conversations(source)
    if not conversations:
        _log(
            f"No conversations recognised in {source}. The dump layout may have "
            "changed; inspect it and extend walk_conversations() in official.py."
        )
        return 1

    out: Path = args.out
    raw_dir = out / "raw"
    for conversation in conversations:
        if conversation.id:
            # Same envelope `pull` writes, so `render` and `merge` can read
            # either source without caring which produced the archive.
            render.write_raw(raw_dir, conversation.id, conversation.raw)
    _write_outputs(out, conversations, not args.no_markdown)
    _log(f"{len(conversations)} conversation(s) written to {out}/")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    out: Path = args.out
    raw_dir = out / "raw"
    if not raw_dir.is_dir():
        _log(f"error: {raw_dir} does not exist. Run `pull` first.")
        return 1

    conversations = [
        conversation
        for path in sorted(raw_dir.glob("*.json"))
        if (conversation := _load_raw(path)) is not None
    ]
    if not conversations:
        _log(f"error: no readable payloads in {raw_dir}.")
        return 1

    _write_outputs(out, conversations, markdown=True)
    _log(f"Re-rendered {len(conversations)} conversation(s) into {out}/markdown/")
    return 0


def _load_archive(out: Path) -> list[Conversation] | None:
    """Every conversation archived under ``out/raw``, or None if there are none."""
    raw_dir = out / "raw"
    if not raw_dir.is_dir():
        _log(f"error: {raw_dir} does not exist. Run `pull` or `convert` first.")
        return None
    conversations = [
        conversation
        for path in sorted(raw_dir.glob("*.json"))
        if (conversation := _load_raw(path)) is not None
    ]
    if not conversations:
        _log(f"error: no readable payloads in {raw_dir}.")
        return None
    return conversations


def cmd_merge(args: argparse.Namespace) -> int:
    conversations = _load_archive(args.out)
    if conversations is None:
        return 1

    groups = merge.group_conversations(conversations, threshold=args.threshold)
    _log(merge.summarize(groups))
    if args.dry_run:
        _log("\n(dry run: nothing written)")
        return 0

    written = merge.write_groups(args.out / "merged", groups)
    _log(f"\n{len(written)} merged document(s) in {args.out}/merged/")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok_export",
        description="Export your Grok (grok.com) chat history to JSON and Markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--out",
            type=Path,
            default=DEFAULT_OUT,
            help=f"output directory (default: {DEFAULT_OUT})",
        )
        sub.add_argument("--no-markdown", action="store_true", help="write JSON only")

    def add_network(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--cookie",
            help=(
                "path to a file holding a 'Copy as cURL' command or a cookie "
                "header (or the cookie string itself). Defaults to $GROK_COOKIE."
            ),
        )
        sub.add_argument(
            "--base-url", default=client_module.BASE_URL, help=argparse.SUPPRESS
        )
        sub.add_argument(
            "--page-size", type=int, default=100, help="conversations per page"
        )
        sub.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="minimum seconds between requests (default: 0.5)",
        )
        sub.add_argument(
            "--list-path",
            action="append",
            help="override the conversation-listing path (repeatable)",
        )
        sub.add_argument(
            "--detail-path",
            action="append",
            help="override the per-conversation path; must contain {id} (repeatable)",
        )

    probe = subparsers.add_parser(
        "probe", help="fetch one listing page and print it raw"
    )
    add_network(probe)
    probe.set_defaults(func=cmd_probe)

    pull = subparsers.add_parser("pull", help="export every conversation")
    add_network(pull)
    add_common(pull)
    pull.add_argument("--limit", type=int, help="stop after N conversations")
    pull.add_argument(
        "--refresh",
        action="store_true",
        help="re-fetch conversations already archived under raw/",
    )
    pull.set_defaults(func=cmd_pull)

    convert = subparsers.add_parser(
        "convert", help="convert an official xAI data export (.zip, dir, or .json)"
    )
    convert.add_argument("source", type=Path, help="the downloaded archive or file")
    add_common(convert)
    convert.set_defaults(func=cmd_convert)

    merge_cmd = subparsers.add_parser(
        "merge", help="group similar conversations and merge each group into one file"
    )
    add_common(merge_cmd)
    merge_cmd.add_argument(
        "--threshold",
        type=float,
        default=merge.DEFAULT_THRESHOLD,
        help=(
            "similarity needed to merge, 0-1 "
            f"(default: {merge.DEFAULT_THRESHOLD}; lower merges more)"
        ),
    )
    merge_cmd.add_argument(
        "--dry-run", action="store_true", help="report the grouping without writing"
    )
    merge_cmd.set_defaults(func=cmd_merge)

    render_cmd = subparsers.add_parser(
        "render", help="rebuild Markdown from an earlier export's raw/ directory"
    )
    add_common(render_cmd)
    render_cmd.set_defaults(func=cmd_render)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except AuthError as error:
        _log(f"error: {error}")
        return 2
    except GrokError as error:
        _log(f"error: {error}")
        return 1
    except KeyboardInterrupt:
        _log("Interrupted.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
