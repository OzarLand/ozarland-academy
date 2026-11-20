#!/usr/bin/env python3
"""Rewrite the links of the pages after a repository is moved into a module.

Each module of the academy, except day2, was a repository of its own:

    lab         OzarLand/openstack-quick-lab
    deploy      OzarLand/kolla-ansible-deployment-patterns
    runbooks    OzarLand/openstack-vm-runbooks
    production  OzarLand/production-guide

Its history is imported under docs/<module>/ by git filter-repo, with every
README.md renamed index.md and the files the academy already has (LICENSE,
CODE_OF_CONDUCT.md) left out. The pages still link the way they did in their
repository. This script rewrites, in every page under docs/:

* a relative link to a README.md that is now an index.md;
* a relative link to a file that was left out: LICENSE to the licence of this
  repository, CODE_OF_CONDUCT.md to the one of the hub (OzarLand/ozarland);
* an absolute link to a file of a moved repository
  (https://github.com/OzarLand/<repository>/blob|tree/main/<path>) whose
  module is available:
    - a page of the same module: a relative link to its .md file;
    - a page of another module: the relative address of its page, ending
      with "/" (rule link-site of check_docs.py);
    - any other file (a script): a link to it in this repository, on GitHub
      (rule link-repo-file);
  a link to the repository itself leads to the home page of the module.

Links inside code (fenced blocks, inline code) are not touched: a command
such as `git clone` is updated by hand. Links to the issues, pull requests or
discussions of a moved repository stay: the repository is archived, not
deleted. A link that cannot be mapped (the file does not exist any more) is
listed and left as it is.

Usage:  python3 tools/site/rewrite_links.py            show what would change
        python3 tools/site/rewrite_links.py --apply    write the changes

Run it once after each import; it is idempotent. Standard library only.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

ORG = "OzarLand"
REPOSITORY = f"https://github.com/{ORG}/ozarland-academy"
HUB = f"https://github.com/{ORG}/ozarland"

#: Repository that each module was before it moved into the academy.
SOURCES = {
    "openstack-quick-lab": "lab",
    "kolla-ansible-deployment-patterns": "deploy",
    "openstack-vm-runbooks": "runbooks",
    "production-guide": "production",
}

#: Files of a moved repository that were left out of the import, and where a
#: link to them goes now.
DROPPED = {
    "LICENSE": f"{REPOSITORY}/blob/main/LICENSE",
    "CODE_OF_CONDUCT.md": f"{HUB}/blob/main/CODE_OF_CONDUCT.md",
}

_SOURCE_NAMES = "|".join(re.escape(name) for name in SOURCES)
ABSOLUTE = re.compile(
    rf"https?://github\.com/{ORG}/(?P<repo>{_SOURCE_NAMES})"
    r"(?:(?P<kind>/(?:blob|tree)/main)(?P<path>/[^\s)\"'<>#]*)?)?/?(?P<fragment>#[^\s)\"'<>]*)?"
    r"(?=[\s)\"'<>]|$)",
    re.IGNORECASE,
)
#: Inline link or image target, HTML href/src, reference definition.
TARGETS = (
    re.compile(r"\]\((?P<url><[^>]+>|[^)\s]+)"),
    re.compile(r"\b(?:href|src)=\"(?P<url>[^\"]+)\""),
    re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(?P<url>\S+)"),
)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")


def renamed(path: str) -> str:
    """Path of a file of a moved repository after the import (README.md -> index.md)."""
    head, name = posixpath.split(path)
    if name == "README.md":
        return posixpath.join(head, "index.md") if head else "index.md"
    return path


class Rewriter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry = releases.load_registry(root)
        self.available = {m.id for m in self.registry.modules if not m.versioned and m.available}
        self.unmapped: list[str] = []

    # -- targets ------------------------------------------------------------

    def _module_of(self, source: str) -> str | None:
        parts = source.split("/")
        return parts[1] if len(parts) > 2 and parts[0] == "docs" else None

    def _target(self, source: str, module: str, path: str, fragment: str) -> str | None:
        """Link from the page `source` to `path`, a file or directory of `module` (as in docs/<module>/)."""
        path = path.strip("/")
        if path in DROPPED:
            return DROPPED[path] + fragment
        path = renamed(path)
        target = posixpath.join("docs", module, path) if path else f"docs/{module}"
        full = self.root / target
        if full.is_dir():
            if (full / "index.md").is_file():
                target = posixpath.join(target, "index.md")
            else:
                return f"{REPOSITORY}/tree/main/{target}{fragment}"
        elif not full.is_file():
            return None
        if not target.endswith(".md"):
            return f"{REPOSITORY}/blob/main/{target}{fragment}"
        base = posixpath.dirname(source)
        if self._module_of(source) == module:
            return posixpath.relpath(target, base) + fragment
        page = releases.page_url(Path(target).relative_to(f"docs/{module}"))
        address = posixpath.relpath(posixpath.join("docs", module, page), base)
        return address + "/" + fragment

    def _absolute(self, source: str, match: re.Match) -> str | None:
        module = SOURCES[match.group("repo")]
        if module not in self.available:
            return None
        path = match.group("path") or ""
        fragment = match.group("fragment") or ""
        if not match.group("kind") and path:
            return None
        return self._target(source, module, path, fragment)

    def _relative(self, source: str, url: str) -> str | None:
        if re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", url, re.IGNORECASE):
            return None
        path, _, fragment = url.partition("#")
        fragment = f"#{fragment}" if fragment else ""
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        if (self.root / resolved).exists():
            return None
        name = posixpath.basename(path)
        if name in DROPPED:
            return DROPPED[name] + fragment
        if name == "README.md":
            index = posixpath.join(posixpath.dirname(resolved), "index.md")
            if (self.root / index).is_file():
                return posixpath.join(posixpath.dirname(path), "index.md") + fragment
        return None

    # -- files ----------------------------------------------------------------

    def rewrite(self, source: str, text: str) -> str:
        lines = text.split("\n")
        fence = None
        for index, line in enumerate(lines):
            marker = FENCE.match(line)
            if fence:
                if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                    fence = None
                continue
            if marker:
                fence = marker.group(1)
                continue
            lines[index] = self._line(source, index + 1, line)
        return "\n".join(lines)

    def _line(self, source: str, number: int, line: str) -> str:
        # Inline code is kept as it is: only the text between code spans is rewritten.
        pieces = []
        last = 0
        for code in INLINE_CODE.finditer(line):
            pieces.append(self._text(source, number, line[last : code.start()]))
            pieces.append(code.group(0))
            last = code.end()
        pieces.append(self._text(source, number, line[last:]))
        return "".join(pieces)

    def _text(self, source: str, number: int, text: str) -> str:
        def absolute(match: re.Match) -> str:
            new = self._absolute(source, match)
            if new is None:
                if match.group("kind") and SOURCES[match.group("repo")] in self.available:
                    self.unmapped.append(f"{source}:{number}: {match.group(0)}")
                return match.group(0)
            return new

        text = ABSOLUTE.sub(absolute, text)
        for pattern in TARGETS:
            def relative(match: re.Match) -> str:
                url = match.group("url")
                bare = url[1:-1] if url.startswith("<") else url
                new = self._relative(source, bare)
                if new is None:
                    return match.group(0)
                start, end = match.span("url")
                whole = match.group(0)
                offset = match.start()
                return whole[: start - offset] + new + whole[end - offset :]

            text = pattern.sub(relative, text)
        return text

    def run(self, apply: bool) -> int:
        changed = 0
        for path in sorted((self.root / "docs").rglob("*.md")):
            source = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8")
            new = self.rewrite(source, text)
            if new != text:
                changed += 1
                old_lines, new_lines = text.split("\n"), new.split("\n")
                for number, (a, b) in enumerate(zip(old_lines, new_lines), start=1):
                    if a != b:
                        print(f"{source}:{number}\n  - {a.strip()}\n  + {b.strip()}")
                if apply:
                    path.write_text(new, encoding="utf-8")
        for line in self.unmapped:
            print(f"not mapped (the file does not exist): {line}", file=sys.stderr)
        verb = "rewritten" if apply else "to rewrite (--apply writes them)"
        print(f"rewrite_links: {changed} file(s) {verb}, {len(self.unmapped)} link(s) not mapped")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return Rewriter(args.root).run(args.apply)


if __name__ == "__main__":
    sys.exit(main())
