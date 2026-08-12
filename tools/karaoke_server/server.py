"""HTTP shell for the shared karaoke leaderboard.

Serves the karaoke page and the score API from one origin, so a room full
of phones pointed at the same host share a board with no CORS involved.
Cross-origin use is still allowed for pointing a page hosted elsewhere at
a central server.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .board import Board, ValidationError

MAX_BODY = 8 * 1024
REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "static" / "karaoke-box.html"

# Tells the page it has somewhere to post scores. Absent when the file is
# opened straight from disk, which is what keeps the standalone copy silent
# rather than firing doomed requests at nothing.
BOARD_META = '<meta name="karaoke-board" content="/api/scores">'

HEAD = (
    '<!doctype html>\n<html lang="en">\n<head>\n'
    '<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    + BOARD_META
    + "\n"
)


def page_html(source=None):
    """The karaoke page as a standalone document, told where to post scores.

    The file is authored as an artifact fragment -- title and styles, then
    markup, with no <html> around it. Served raw it would land in quirks
    mode and lay out wrongly, so head and body are split at the stylesheet
    and wrapped properly.
    """
    html = source if source is not None else PAGE.read_text(encoding="utf-8")
    marker = "</style>"
    cut = html.find(marker)
    if cut == -1:
        # no stylesheet to split on; wrap whole and let the parser hoist
        return HEAD + "</head>\n<body>\n" + html + "\n</body>\n</html>\n"
    cut += len(marker)
    return (
        HEAD + html[:cut] + "\n</head>\n<body>\n" + html[cut:] + "\n</body>\n</html>\n"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "KaraokeBoard/1.0"
    board: Board = None
    origin = "*"

    def log_message(self, fmt, *args):
        if os.environ.get("KARAOKE_QUIET"):
            return
        super().log_message(fmt, *args)

    # ---- helpers ----
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", self.origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status, text):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---- routes ----
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        route = urlparse(self.path)
        if route.path in ("/", "/index.html"):
            if not PAGE.exists():
                self._html(404, "<h1>karaoke-box.html not found</h1>")
                return
            self._html(200, page_html())
        elif route.path == "/api/scores":
            limit = parse_qs(route.query).get("limit", ["20"])[0]
            try:
                limit = int(limit)
            except ValueError:
                limit = 20
            self._json(200, {"scores": self.board.top(limit)})
        elif route.path == "/favicon.ico":
            # browsers ask unprompted; a 404 here is just console noise
            self.send_response(204)
            self.end_headers()
        elif route.path == "/healthz":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/scores":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"error": "body must be 1..%d bytes" % MAX_BODY})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "body must be JSON"})
            return
        try:
            entry = self.board.add(payload)
        except ValidationError as err:
            self._json(400, {"error": str(err)})
            return
        self._json(201, {"entry": entry, "scores": self.board.top(20)})


def build(db_path, origin="*"):
    """A handler class bound to one board -- handy for tests."""
    return type("BoundHandler", (Handler,), {"board": Board(db_path), "origin": origin})


def serve(host="0.0.0.0", port=8770, db_path=None, origin="*"):
    db_path = db_path or os.environ.get("KARAOKE_DB", "karaoke-scores.json")
    httpd = ThreadingHTTPServer((host, port), build(db_path, origin))
    shown = "localhost" if host in ("0.0.0.0", "") else host
    print(f"Karaoke board on http://{shown}:{port}  (scores in {db_path})")
    print("Open that address on any device on the same network to share a board.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
