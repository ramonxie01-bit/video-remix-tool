"""Local review server. Bind 127.0.0.1 only. file:// cannot save notes."""
from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.review.board import write_csv
from app.review.bundle import (
    merge_notes_into_plan,
    notes_path_for,
    plan_path_for,
    read_notes,
    review_dir,
    sanitize_notes,
    write_notes,
)

_lock = threading.Lock()
_state: dict = {}
_MAX_BODY = 2_000_000


def _make_handler(out_dir: Path):
    root = Path(out_dir)
    notes_path = notes_path_for(root)
    plan_path = plan_path_for(root)
    csv_path = review_dir(root) / "审片清单.csv"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/notes":
                self._json(200, read_notes(notes_path))
                return
            # Redirect so the browser URL stays under /_review/ and thumb
            # paths (thumbs/*.jpg, ../remix_*.mp4) resolve inside out_dir.
            if path in ("/", "", "/review.html"):
                self.send_response(302)
                self.send_header("Location", "/_review/review.html")
                self.end_headers()
                return
            return super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/save":
                self._json(404, {"ok": False, "error": "not found"})
                return
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                n = 0
            if n > _MAX_BODY:
                self._json(413, {"ok": False, "error": "too large"})
                return
            raw = self.rfile.read(n) if n else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "invalid json"})
                return
            if not isinstance(data, dict):
                self._json(400, {"ok": False, "error": "invalid json"})
                return
            notes = sanitize_notes(data)
            try:
                write_notes(notes_path, notes)
                if plan_path.is_file() and csv_path.is_file():
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    write_csv(csv_path, plan, notes)
                merge_notes_into_plan(plan_path, notes)
            except OSError as ex:
                self._json(500, {"ok": False, "error": str(ex)})
                return
            self._json(200, {"ok": True, "path": str(notes_path)})

    return Handler


def stop_review_server() -> None:
    with _lock:
        httpd = _state.get("httpd")
        _state.clear()
    if httpd is not None:
        httpd.shutdown()
        httpd.server_close()


def ensure_review_server(out_dir: Path) -> str:
    """Start or reuse a localhost server rooted at ``out_dir``. Returns the page URL."""
    out_dir = Path(out_dir).resolve()
    old = None
    with _lock:
        current = _state.get("out_dir")
        httpd = _state.get("httpd")
        if httpd is not None and current == out_dir:
            return str(_state["url"])
        old = httpd
        _state.clear()
    if old is not None:
        old.shutdown()
        old.server_close()
    handler = _make_handler(out_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, name="review-board", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/review.html"
    with _lock:
        previous = _state.get("httpd")
        _state.update({"httpd": server, "out_dir": out_dir, "url": url, "thread": thread})
    if previous is not None and previous is not server:
        previous.shutdown()
        previous.server_close()
    return url


def open_review_board(out_dir: Path, *, open_browser: bool = True) -> str:
    """Open the board for an output folder that already has ``_review/plan.json``."""
    plan = plan_path_for(out_dir)
    if not plan.is_file():
        raise FileNotFoundError(
            "还没有审片数据。请先生成混剪，或确认输出目录里已有 _review\\plan.json。"
        )
    url = ensure_review_server(out_dir)
    if open_browser:
        webbrowser.open(url)
    return url
