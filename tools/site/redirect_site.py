#!/usr/bin/env python3
"""Write the site that redirects the former Kolla-Ansible Academy to the portal.

Kolla-Ansible Academy was published by the repository
OzarLand/kolla-ansible-academy at https://ozarland.github.io/kolla-ansible-academy/
before it became the module day2 of OzarLand Academy. GitHub Pages does not
redirect the site of a moved repository, so that repository publishes this
small site instead of its own: one page per address the former site had, each
sending the reader to the same page in the portal.

    <former>/                        -> <portal>day2/
    <former>/<release>/<page>/       -> <portal>day2/<release>/<page>/
    <former>/<page>/ (no release)    -> <portal>day2/<unprefixed>/<page>/

The former site had no release in the addresses of its first version; they
led to Ussuri (UNPREFIXED). Every page of every available release of day2 is
written, as is the home of every planned release. Each page redirects with a
<meta http-equiv="refresh"> (no script needed), keeps the query and the
fragment of the address with a script, says rel="canonical" and noindex, and
shows the link for a reader whose browser does nothing. 404.html covers any
other address of the former site with the same rules, by script.

The address of the portal is the one of the build (SITE_DOMAIN, see
tools/site/README.md): run it once the custom domain serves the portal, so
that the former site sends readers straight to their final address.

Usage:  python3 tools/site/redirect_site.py OUT_DIR [--to URL]
        (OUT_DIR is written from scratch; --to defaults to the portal address)

Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

#: Path of the former site on its host.
FORMER_PATH = "/kolla-ansible-academy/"
#: Release that the addresses without a release led to.
UNPREFIXED = "ussuri"
#: The versioned module that the former site became.
MODULE = "day2"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved to OzarLand Academy</title>
<meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace({target_js} + location.search + location.hash);</script>
<style>body{{font:1rem/1.5 system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#152a50;background:#fbf4e4}}a{{color:#0f62a6}}</style>
</head>
<body>
<h1>Kolla-Ansible Academy has moved</h1>
<p>It is now part of OzarLand Academy: <a href="{target}">{target}</a></p>
</body>
</html>
"""

NOT_FOUND = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved to OzarLand Academy</title>
<meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>
(function () {{
  var data = {data};
  var path = location.pathname;
  var rest = path.indexOf(data.former) === 0 ? path.slice(data.former.length) : "";
  var first = rest.split("/")[0];
  var target = data.portal + data.module + "/";
  if (rest && data.releases.indexOf(first) !== -1) target += rest;
  else if (rest) target += data.unprefixed + "/" + rest;
  location.replace(target + location.search + location.hash);
}})();
</script>
<style>body{{font:1rem/1.5 system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#152a50;background:#fbf4e4}}a{{color:#0f62a6}}</style>
</head>
<body>
<h1>Kolla-Ansible Academy has moved</h1>
<p>It is now part of OzarLand Academy: <a href="{home}">{home}</a></p>
</body>
</html>
"""


def page(target: str) -> str:
    return PAGE.format(target=html.escape(target), target_js=json.dumps(target))


def redirects(root: Path, registry: releases.Registry, portal: str) -> dict[str, str]:
    """Path in the former site (relative, "" for its root) -> address in the portal."""
    module = next((m for m in registry.modules if m.id == MODULE), None)
    if module is None or not module.versioned:
        raise releases.RegistryError([f"`{MODULE}` is not the versioned module of {releases.REGISTRY_FILE}"])
    home = f"{portal}{MODULE}/"
    out = {"": home}
    unprefixed = None
    for release in registry.releases:
        if release.module != MODULE:
            continue
        out[f"{release.id}/"] = f"{portal}{release.path}/"
        if not release.available:
            continue
        for url in releases.page_urls(root, release):
            out[f"{release.id}/{url}"] = f"{portal}{release.path}/{url}"
        if release.id == UNPREFIXED:
            unprefixed = release
    if unprefixed is None:
        raise releases.RegistryError([f"`{MODULE}/{UNPREFIXED}` is not an available release"])
    for url in releases.page_urls(root, unprefixed):
        if url and url.split("/")[0] not in {r.id for r in registry.releases}:
            out.setdefault(url, f"{portal}{unprefixed.path}/{url}")
    return out


def write_site(out_dir: Path, root: Path, portal: str) -> int:
    registry = releases.load_registry(root)
    pages = redirects(root, registry, portal)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for rel, target in pages.items():
        path = out_dir / rel / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page(target), encoding="utf-8")
    data = {
        "former": FORMER_PATH,
        "portal": portal,
        "module": MODULE,
        "unprefixed": UNPREFIXED,
        "releases": sorted({r.id for r in registry.releases if r.module == MODULE}),
    }
    home = f"{portal}{MODULE}/"
    (out_dir / "404.html").write_text(
        NOT_FOUND.format(data=json.dumps(data), home=html.escape(home)), encoding="utf-8"
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return len(pages)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=Path, help="directory to write (replaced)")
    parser.add_argument("--to", help="address of the portal root (default: the address of the build)")
    parser.add_argument("--root", type=Path, default=releases.ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        portal = args.to or releases.portal_root_url(releases.load_project(args.root / releases.BASE_CONFIG))
    except releases.RegistryError as exc:
        sys.exit("redirect_site: " + "; ".join(exc.problems))
    if not portal.startswith("https://"):
        sys.exit(f"redirect_site: the address of the portal must start with https:// ({portal})")
    if not portal.endswith("/"):
        portal += "/"
    try:
        count = write_site(args.out, args.root, portal)
    except releases.RegistryError as exc:
        sys.exit("redirect_site: " + "; ".join(exc.problems))
    print(f"redirect_site: {count} page(s) and 404.html written to {args.out}, redirecting to {portal}{MODULE}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
