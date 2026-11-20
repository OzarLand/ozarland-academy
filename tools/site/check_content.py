#!/usr/bin/env python3
"""Run the content checks of the OzarLand hub on the modules that came from it.

The pages of Deployment patterns (deploy) and VM runbooks (runbooks) follow the
community content conventions of the hub, OzarLand/ozarland: a `kind` in the
front matter (pattern, runbook...), its required fields and sections, risk
markers that match the declared risk. The hub's checker,
tools/check_content.py, checks them, and also looks for sensitive data (IP and
MAC addresses outside the documentation ranges, secrets) in any text file.

This script loads that checker from a checkout of the hub and runs it on
docs/<module>/ of each available module whose former repository ran it in
its CI: deploy and runbooks. The other modules never followed these
conventions: their pages have no `kind`, and the lab's scripts use private
lab subnets (10.98.0.0/16, 10.99.0.0/16) on purpose.

Two things differ from a run on the former repository:

* index.md is the index page of a directory (it was README.md), not a page
  with a `kind`;
* links are not checked here: check_docs.py checks them, including the links
  between modules, which the hub's checker cannot resolve.

Usage:  python3 tools/site/check_content.py --hub <checkout of OzarLand/ozarland>

CI checks out the hub next to the repository (.github/workflows/docs.yml).
Exit status: 0 when there is no error, 1 otherwise. Standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

#: Modules checked: those whose former repository ran the hub's checker.
MODULES = ("deploy", "runbooks")


def load_checker(hub: Path):
    path = hub / "tools" / "check_content.py"
    if not path.is_file():
        sys.exit(f"check_content: {path} not found (--hub is a checkout of OzarLand/ozarland)")
    spec = importlib.util.spec_from_file_location("hub_check_content", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.NON_PAGES = set(module.NON_PAGES) | {"index.md"}
    module.check_links = lambda root, rel: []
    return module


def check_module(checker, docs: Path) -> tuple[list[str], list[str], int, int]:
    errors: list[str] = []
    warnings: list[str] = []
    files = []
    for directory, dirs, names in os.walk(docs):
        dirs[:] = [d for d in dirs if d not in (".git", "assets")]
        files += [os.path.relpath(os.path.join(directory, name), docs) for name in names]
    pages = 0
    for rel in sorted(files):
        if rel.endswith((".md", ".yml", ".yaml", ".txt", ".cfg", ".conf", ".ini", ".sh", ".py", ".j2", ".env")):
            errors += checker.check_sensitive(str(docs), rel)
        if checker.is_page(rel):
            pages += 1
            page_errors, page_warnings = checker.check_page(str(docs), rel)
            errors += page_errors
            warnings += page_warnings
    return errors, warnings, pages, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--hub", type=Path, required=True, help="checkout of OzarLand/ozarland")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    checker = load_checker(args.hub)
    registry = releases.load_registry(args.root)
    available = {m.id for m in registry.modules if not m.versioned and m.available}
    failed = False
    for module in MODULES:
        if module not in available:
            continue
        docs = args.root / "docs" / module
        with contextlib.redirect_stdout(io.StringIO()):
            errors, warnings, pages, files = check_module(checker, docs)
        for line in errors:
            print(f"ERROR   docs/{module}/{line}")
        for line in warnings:
            print(f"WARNING docs/{module}/{line}")
        print(f"{module}: {pages} page(s), {files} file(s): {len(errors)} error(s), {len(warnings)} warning(s)")
        failed = failed or bool(errors)
    print("check_content: " + ("FAILED" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
