"""Tiny static-file server hosting the three HTML frontends on 3001/3002/3003."""

from __future__ import annotations

import http.server
import os
import socketserver
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontends"

MOUNTS = {
    3001: ROOT / "partner_site",
    3002: ROOT / "glchat_admin",
    3003: ROOT / "glchat_widget",
}


def serve(port: int, directory: Path):
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(directory), **kw)
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"Serving {directory.name} on http://localhost:{port}")
        httpd.serve_forever()


def main():
    threads = []
    for port, path in MOUNTS.items():
        t = threading.Thread(target=serve, args=(port, path), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
