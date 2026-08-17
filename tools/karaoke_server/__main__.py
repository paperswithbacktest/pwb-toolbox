"""Entry point: python -m tools.karaoke_server [--port N] [--db PATH]"""

import argparse

from .server import serve


def main():
    parser = argparse.ArgumentParser(
        prog="python -m tools.karaoke_server",
        description="Serve the karaoke page and a shared leaderboard.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--db", default=None, help="where scores are kept")
    parser.add_argument(
        "--origin",
        default="*",
        help="Access-Control-Allow-Origin for pages served from elsewhere",
    )
    args = parser.parse_args()
    serve(host=args.host, port=args.port, db_path=args.db, origin=args.origin)


if __name__ == "__main__":
    main()
