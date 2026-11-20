#!/usr/bin/env python3
"""Prepare the sources before the sites of the portal are built.

1. Vendored Mermaid: ``overrides/assets/vendor/mermaid/mermaid.min.js`` is not
   committed. When it is missing (or is not the pinned release) it is fetched
   by ``tools/site/fetch_vendor.py``, which verifies it. This is the only
   step that may need the network; ``--skip-vendor`` turns it off. The file is
   shared by all sites.

2. ``docs/<path>/assets/data/updates.json``, one per available site: for
   every Markdown page of the release, the date of the last commit that
   changed it. The page template shows it as "Last updated" and the home page
   of the release lists the most recently updated pages
   (overrides/assets/javascripts/portal.js reads the file in the browser; the
   release selector also reads the file of another release to know whether
   that release has the page being read).

    {
      "generated": "<ISO 8601 date of the HEAD commit>",
      "pages": [
        {"path": "operations/reconfigure-nova.md",
         "url": "operations/reconfigure-nova/",
         "title": "Reconfigure Nova",
         "updated": "YYYY-MM-DD"}
      ]
    }

Properties of updates.json:

* reproducible: every value comes from the Git history and the files, never
  from the wall clock, so the same commit always gives the same file;
* one pass over the history (a single ``git log``), whatever the page count;
* a commit that only moves a file (a rename without a change of content, as
  when the pages moved to ``docs/day2/<id>/``) is not an update of the page: the
  date is the one of the last commit that changed its content, under any
  earlier name;
* shallow clones: a page whose last change is not in the fetched history gets
  the date of the HEAD commit (use a full clone, e.g. ``fetch-depth: 0`` in
  CI, for exact dates);
* standard library only.

3. ``docs/<path>/assets/data/glossary.json``, one per available site: the
   terms of the release's glossary, for the definitions shown on hover
   (tools/site/glossary.py describes the file).

These outputs are generated: they are git-ignored and must not be edited.

Usage (from anywhere):

    python3 tools/site/prebuild.py                    every available site of academy.toml
    python3 tools/site/prebuild.py --release day2/ussuri   one site (repeatable)
    python3 tools/site/prebuild.py --docs-dir DIR     a docs directory that is not in the registry
    ... [--skip-vendor]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

# The registry of the portal is read by releases.py, next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402
import glossary  # noqa: E402
from releases import INDEX_NAMES, SKIPPED_TOP_DIRS, page_url  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[2]
COMMIT_MARK = "\x01"


def load_fetch_vendor():
    """The module tools/site/fetch_vendor.py (it sits next to this file)."""
    spec = importlib.util.spec_from_file_location(
        "fetch_vendor", Path(__file__).resolve().with_name("fetch_vendor.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_vendor(root: Path) -> bool:
    """Put the vendored Mermaid bundle in place. False when that failed.

    Nothing is downloaded when the pinned file is already there.
    """
    fetch_vendor = load_fetch_vendor()
    try:
        fetch_vendor.ensure(root)
    except fetch_vendor.VendorError as error:
        print(f"prebuild: error: {error}", file=sys.stderr)
        print(
            "prebuild: the pages with a diagram need the vendored Mermaid bundle; "
            "see overrides/assets/vendor/mermaid/README.md (or pass --skip-vendor)",
            file=sys.stderr,
        )
        return False
    return True


def git(root: Path, *args: str) -> str | None:
    """Run git in `root`; None when git or the repository is unavailable."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def last_commit_dates(root: Path, docs_dir: str) -> dict[str, str]:
    """Map each path under `docs_dir` to the date of the last commit that changed it.

    Single ``git log`` pass, newest commit first: the first time a path is
    seen is its last change. A rename is followed: the commit that renames a
    file counts only when it also changes its content, and older commits
    count under the former name. Renames are looked for inside the top-level
    directory of `docs_dir` (``docs`` for ``docs/ussuri``). Commits at the
    edge of a shallow clone list the whole tree as added, so they say nothing
    about a file and are skipped.
    """
    log = git(
        root,
        "log",
        f"--format={COMMIT_MARK}%H %cI",
        "--name-status",
        "--find-renames",
        "--relative",  # paths relative to `root`, even inside a larger repository
        "--",
        docs_dir.split("/")[0],
    )
    if log is None:
        return {}
    shallow_file = git(root, "rev-parse", "--git-path", "shallow")
    boundary: set[str] = set()
    if shallow_file:
        path = Path(shallow_file.strip())
        path = path if path.is_absolute() else root / path
        if path.is_file():
            boundary = set(path.read_text(encoding="utf-8").split())

    dates: dict[str, str] = {}
    # Former name of a file -> its name today, for the renames seen so far.
    today: dict[str, str] = {}
    current: str | None = None
    for line in log.splitlines():
        if line.startswith(COMMIT_MARK):
            sha, _, iso = line[1:].partition(" ")
            current = None if sha in boundary else iso[:10]
            continue
        fields = line.split("\t")
        if current is None or len(fields) < 2:
            continue
        status = fields[0]
        if status.startswith("R") and len(fields) == 3:
            former, name = fields[1], fields[2]
            final = today.pop(name, name)
            today[former] = final
            if status != "R100":
                dates.setdefault(final, current)
        else:
            name = fields[-1]
            dates.setdefault(today.get(name, name), current)
            if status.startswith(("A", "C")):
                # The file starts here: an older file of the same name is another file.
                today.pop(name, None)
    return dates


def front_matter_title(text: str) -> str | None:
    """`title` of the YAML front matter (plain or quoted scalar on one line)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = re.search(r"^title:[ \t]*(.+?)[ \t]*$", text[3:end], re.MULTILINE)
    if not match:
        return None
    value = match.group(1)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return re.sub(r"\s+#.*$", "", value) or None


def first_heading(text: str) -> str | None:
    """Text of the first `# ` heading outside fenced code."""
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and line.startswith("# "):
            return re.sub(r"[`*_]", "", line[2:]).strip() or None
    return None


def collect(root: Path, docs_dir: str) -> dict:
    docs = root / docs_dir
    head = git(root, "log", "-1", "--format=%cI")
    head = head.strip() if head else None
    # Newer Git writes a UTC offset as "Z"; keep one spelling in the output.
    if head and head.endswith("Z"):
        head = head[:-1] + "+00:00"
    if head is None:
        print("prebuild: no Git history available; pages get no date", file=sys.stderr)
    dates = last_commit_dates(root, docs_dir) if head else {}

    pages = []
    missing = 0
    for path in sorted(docs.rglob("*.md")):
        rel = path.relative_to(docs)
        if rel.parts[0] in SKIPPED_TOP_DIRS:
            continue
        text = path.read_text(encoding="utf-8")
        updated = dates.get(f"{docs_dir}/{rel.as_posix()}")
        if updated is None and head:
            # Not committed yet, or last changed before the fetched history.
            updated = head[:10]
            missing += 1
        pages.append(
            {
                "path": rel.as_posix(),
                "url": page_url(rel),
                "title": front_matter_title(text) or first_heading(text) or rel.stem,
                "updated": updated,
            }
        )
    if missing and head:
        print(
            f"prebuild: {missing} page(s) without a commit in the available history "
            f"use the HEAD date {head[:10]}",
            file=sys.stderr,
        )
    return {"generated": head, "pages": pages}


def write_updates(root: Path, docs_dir: str, output: Path | None = None) -> int:
    """Write updates.json of one docs directory. Returns the number of pages."""
    output = output or root / docs_dir / "assets/data/updates.json"
    data = collect(root, docs_dir)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file() or output.read_text(encoding="utf-8") != content:
        output.write_text(content, encoding="utf-8")
    print(f"prebuild: {len(data['pages'])} pages -> {output.relative_to(root)}")
    return len(data["pages"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument(
        "--release",
        action="append",
        metavar="PATH",
        help="site of academy.toml to prepare, such as day2/ussuri (default: every available site)",
    )
    parser.add_argument(
        "--docs-dir",
        action="append",
        metavar="DIR",
        help="docs directory, relative to the root, to prepare instead of the sites of the registry",
    )
    parser.add_argument(
        "--skip-vendor",
        action="store_true",
        help="do not fetch the vendored Mermaid bundle (diagrams will not render without it)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.docs_dir:
        if args.release:
            parser.error("--release and --docs-dir cannot be used together")
        docs_dirs = [value.strip("/") for value in args.docs_dir]
    else:
        try:
            registry = releases.load_registry(root)
            selected = [
                release
                for name in (args.release or [None])
                for release in releases.select(registry, name)
            ]
        except releases.RegistryError as error:
            for problem in error.problems:
                print(f"prebuild: {releases.REGISTRY_FILE}: {problem}", file=sys.stderr)
            return 1
        docs_dirs = [release.docs_dir for release in selected]
    for docs_dir in docs_dirs:
        if not (root / docs_dir).is_dir():
            print(f"prebuild: {root / docs_dir} is not a directory", file=sys.stderr)
            return 1
    if not args.skip_vendor and not ensure_vendor(root):
        return 1
    for docs_dir in docs_dirs:
        write_updates(root, docs_dir)
        glossary.write_glossary(root, docs_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
