#!/usr/bin/env python
"""Dev audition server — play the generated wavetables in the browser.

NOT part of the product or `verify.py`; a convenience for the Run-1 audition
checkpoint so you can hear the library without Serum. It is a read-only "third
skin": it serves the catalog, the wav tables, and the spectrograms from out/ to
a small Web-Audio wavetable synth (static/), which decodes the exact 2048-sample
frames and lets you scrub the morph while holding a note.

    python tools/audition/server.py            # opens http://localhost:8731

Run `python -m wtfoundry.cli build` first so out/ is populated.
"""

from __future__ import annotations

import argparse
import socketserver
import webbrowser
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8731

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".wav": "audio/wav",
    ".png": "image/png",
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        self._send(path.read_bytes(), _CTYPES.get(path.suffix, "application/octet-stream"))

    def do_GET(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0]
        try:
            if route in ("/", "/index.html"):
                self._file(STATIC / "index.html")
            elif route == "/app.js":
                self._file(STATIC / "app.js")
            elif route == "/catalog.json":
                self._file(OUT / "catalog.json")
            elif route.startswith("/audio/"):
                self._file(OUT / Path(route[len("/audio/") :]).name)  # .name blocks traversal
            elif route.startswith("/spectro/"):
                self._file(OUT / Path(route[len("/spectro/") :]).name)
            else:
                self._send(b"not found", "text/plain", 404)
        except FileNotFoundError:
            self._send(b"not found", "text/plain", 404)

    def log_message(self, *_args) -> None:  # quiet
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not (OUT / "catalog.json").exists():
        print("WARNING: out/catalog.json not found — run `python -m wtfoundry.cli build` first.")

    url = f"http://localhost:{args.port}"
    print(f"Audition server on {url}  (serving {OUT})\nPress Ctrl+C to stop.")
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as httpd:
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")


if __name__ == "__main__":
    main()
