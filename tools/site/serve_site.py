#!/usr/bin/env python3
"""Serve the built portal locally the way GitHub Pages publishes it.

    python3 tools/site/serve_site.py [site] [--addr HOST:PORT]

The output directory is served under the path of the portal address
(releases.portal_root_url: https://<SITE_DOMAIN>/ or `site_url` of zensical.base.toml,
e.g. http://localhost:8000/ozarland-academy/),
and an unknown address gets the root 404.html with status 404. That page
sends an address under a planned module or release to its only page, which
`python3 -m http.server` would not show.

Standard library only. Not a production server.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files under `prefix`; the root 404.html for everything else."""

    prefix = "/"

    def translate_path(self, path: str) -> str:
        path = unquote(urlsplit(path).path)
        if path + "/" == self.prefix:
            path = self.prefix
        if not path.startswith(self.prefix):
            return str(Path(self.directory) / ".outside-the-portal" / "missing")
        return super().translate_path("/" + path[len(self.prefix) :])

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        page = Path(self.directory) / "404.html"
        if code != 404 or not page.is_file():
            super().send_error(code, message, explain)
            return
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def make_server(site: Path, prefix: str, host: str, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(Handler, directory=str(site))
    handler.func.prefix = prefix  # type: ignore[attr-defined]
    return http.server.ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the built portal as GitHub Pages publishes it.")
    parser.add_argument("site_dir", nargs="?", default=releases.SITE_DIR, help="built portal (default: site)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    parser.add_argument("--addr", default="localhost:8000", help="address to listen on (default: localhost:8000)")
    parser.add_argument("--prefix", default=None, help="URL path of the portal (default: the path of site_url)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    site = (root / args.site_dir).resolve()
    if not (site / "index.html").is_file():
        print(f"serve_site: {site} is not a built portal (run `make docs-build` first)", file=sys.stderr)
        return 1
    prefix = args.prefix
    if prefix is None:
        try:
            prefix = urlsplit(releases.portal_root_url(releases.load_project(root / releases.BASE_CONFIG))).path
        except releases.RegistryError as error:
            print(f"serve_site: {error}", file=sys.stderr)
            return 1
    prefix = "/" + prefix.strip("/") + "/" if prefix.strip("/") else "/"
    host, _, port = args.addr.rpartition(":")
    server = make_server(site, prefix, host or "localhost", int(port))
    print(f"serve_site: http://{host or 'localhost'}:{server.server_address[1]}{prefix}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
