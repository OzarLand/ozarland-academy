#!/usr/bin/env python3
"""Source checks for the Markdown of the portal (no build needed).

The Markdown under docs/<path>/ is the single source of truth and must
work both on github.com and on the generated site. This script reads
academy.toml, then the files of every available site (a module, or a release
of the versioned module) as they are in the working tree, and reports every
place where one of the authoring rules is broken:

    registry        academy.toml can be read, and matches the docs tree: an
                    available site has docs/<path>/ and docs/<path>.toml, a
                    planned one has neither, nothing else is under docs/

    front-matter    every page starts with a YAML front matter block
    title           ... that has a non-empty `title`
    description     ... and a `description` of at most 160 characters
                    (a missing description is a warning until --strict)
    impact          `impact` only uses the documented vocabulary
    tags            `tags` is a list of lowercase names (warning)
    link-file       every relative link points to an existing file
    link-anchor     every `#fragment` is a heading anchor (GitHub slug) or an
                    explicit `<a id="...">` of the target file
    link-style      internal links are relative, stay inside the site
                    (docs/<path>/) and never point to a directory
    link-site       a link to another site of the portal (another release,
                    another module) is the address of its page relative to
                    the file, ending with "/" (../../2023.1/start/conventions/),
                    and that page exists
    link-site-address  no address of the portal is written in full: not in
                    docs/ (links are relative, so the site works on any
                    domain), and outside docs/ only the current address
                    (https://<SITE_DOMAIN>/, or site_url of zensical.base.toml)
    link-reference  `[text][label]` uses a defined label
    link-repo-file  absolute links to a file of this repository (branch main)
                    point to a file that exists
    code-language   every fenced code block has a language
    removed-path    no reference to paths of the old layout (annex/, docs/01-…);
                    inside an HTML comment it is a warning until --strict
    callout         callouts are GitHub alerts of the five known types
    todo-editorial  no leftover `<!-- TODO editorial` marker (warning until
                    --strict)
    nav             every page is in the nav of its site (docs/<path>.toml)
                    and every nav entry exists

Exit status: 0 when there is no error, 1 otherwise. With --strict every
warning is an error. Standard library only (Python 3.11 or newer, for
tomllib).

Usage:  python3 tools/site/check_docs.py [--strict] [--release PATH] [--root DIR]
        python3 tools/site/check_docs.py --list-rules
"""

from __future__ import annotations

import argparse
import difflib
import html
import os
import posixpath
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

if sys.version_info < (3, 11):  # pragma: no cover - depends on the interpreter
    sys.exit("check_docs: Python 3.11 or newer is required (tomllib)")

import tomllib

# The registry of releases lives next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# --- authoring rules -------------------------------------------------------

DESCRIPTION_MAX = 160

#: The five alert types github.com renders (marker alone on its line).
ALERT_TYPES = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")

#: Values allowed in the `impact` front matter list.
IMPACT_VOCABULARY = (
    "read-only",
    "writes-config",
    "pulls-images",
    "restarts-on-drift",
    "recreates-containers",
    "critical",
    "maintenance-window",
    "recovery",
)

#: Paths of the layout that existed before the portal. Nothing may refer to
#: them any more: the files moved under docs/<release>/<section>/.
REMOVED_PATHS = (
    (re.compile(r"(?<![\w.-])annex/"), "annex/"),
    (re.compile(r"(?<![\w-])docs/0[1-9]-"), "docs/0N-..."),
    (re.compile(r"(?<![\w-])docs/10-"), "docs/10-..."),
    (re.compile(r"(?<![\w/-])(?:0[1-9]|10)-[a-z][a-z0-9-]*\.md\b"), "a numbered document file"),
)

#: Markdown files outside docs/ whose links are checked too (when present).
EXTRA_FILES = ("README.md", "CONTRIBUTING.md", "tools/site/README.md")

#: Directories never listed when looking for link targets.
PRUNED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".build"}

RULES = {
    "registry": "academy.toml can be read and matches the docs tree",
    "encoding": "file is UTF-8",
    "front-matter": "page starts with a YAML front matter block that can be read",
    "title": "front matter has a non-empty `title`",
    "description": f"front matter has a `description` of at most {DESCRIPTION_MAX} characters",
    "impact": "`impact` values are in the vocabulary: " + ", ".join(IMPACT_VOCABULARY),
    "tags": "`tags` is a list of lowercase names",
    "link-file": "relative link target exists (exact case)",
    "link-anchor": "link fragment is a heading anchor or an explicit id of the target",
    "link-style": "internal links are relative, inside the site (docs/<path>/), and point to a file",
    "link-site": "link to another site of the portal is the relative address of an existing page (ending with /)",
    "link-site-address": "no address of the portal written in full (only the current one, outside docs/)",
    "link-reference": "reference-style link uses a defined label",
    "link-repo-file": "absolute link to a file of this repository points to an existing file",
    "code-language": "fenced code block has a language and is closed",
    "removed-path": "no reference to a path of the old layout",
    "callout": "callout is a GitHub alert: " + ", ".join(f"[!{t}]" for t in ALERT_TYPES),
    "todo-editorial": "no leftover `<!-- TODO editorial` marker",
    "nav": "page is listed in the nav of its site (docs/<path>.toml), and nav entries exist",
    "config": "configuration of the site can be read",
}

#: Rules reported as warnings unless --strict is given.
WARNING_RULES = {"todo-editorial", "tags"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str
    level: str  # "error" or "warning"


class Report:
    """Findings of one run. With `strict`, warnings are recorded as errors."""

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict
        self.findings: list[Finding] = []

    def error(self, path: str, line: int, rule: str, message: str) -> None:
        self.findings.append(Finding(path, line, rule, message, "error"))

    def warning(self, path: str, line: int, rule: str, message: str) -> None:
        level = "error" if self.strict else "warning"
        self.findings.append(Finding(path, line, rule, message, level))

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f.level == level)


# --- site configuration (zensical.base.toml merged with docs/<id>.toml) ----


class PatternSet:
    """Gitignore-style patterns, as used by `exclude_docs` and `not_in_nav`.

    Supported: `*`, `?`, `**`, a leading `/` (anchor at the docs root), a
    trailing `/` (directory), `#` comments and `!` negation. The last matching
    pattern wins.
    """

    def __init__(self, text: str = "") -> None:
        self.rules: list[tuple[re.Pattern[str], bool]] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            if negated:
                line = line[1:]
            self.rules.append((self._compile(line), not negated))

    @staticmethod
    def _compile(pattern: str) -> re.Pattern[str]:
        directory_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        anchored = "/" in pattern
        pattern = pattern.lstrip("/")
        out = []
        i = 0
        while i < len(pattern):
            if pattern.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
            elif pattern.startswith("**", i):
                out.append(".*")
                i += 2
            elif pattern[i] == "*":
                out.append("[^/]*")
                i += 1
            elif pattern[i] == "?":
                out.append("[^/]")
                i += 1
            else:
                out.append(re.escape(pattern[i]))
                i += 1
        body = "".join(out)
        prefix = "" if anchored else "(?:.*/)?"
        # A pattern also covers everything below a matching directory.
        suffix = "/.*" if directory_only else "(?:/.*)?"
        return re.compile(f"^{prefix}{body}{suffix}$")

    def match(self, rel: str) -> bool:
        result = False
        for regex, value in self.rules:
            if regex.match(rel):
                result = value
        return result


@dataclass
class SiteConfig:
    path: Path
    found: bool = False
    error: str | None = None
    docs_dir: str = "docs"
    site_dir: str = "site"
    site_url: str = ""
    repo_url: str = ""
    use_directory_urls: bool = True
    nav: list | None = None
    exclude: PatternSet = field(default_factory=PatternSet)
    not_in_nav: PatternSet = field(default_factory=PatternSet)
    #: Path shown in the findings (the file that holds the nav).
    name: str = ""
    #: Address of the portal root, the registry (None when unknown) and the
    #: path of the site this configuration builds ("" outside a site).
    portal_url: str = ""
    registry: releases.Registry | None = None
    release: str = ""
    #: Every address of the portal (portal_addresses), without scheme.
    addresses: list[str] = field(default_factory=list)


def load_config(path: Path) -> SiteConfig:
    """Read the `[project]` table of a TOML file (missing file: defaults)."""
    config = SiteConfig(path=path, name=path.name)
    if not path.is_file():
        return config
    config.found = True
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        config.error = str(exc)
        return config
    project = data.get("project", {})
    if not isinstance(project, dict):
        config.error = "`project` is not a table"
        return config
    return apply_project(config, project)


def release_config(root: Path, registry: releases.Registry, release: releases.Release) -> SiteConfig:
    """Configuration of one available site, as the build merges it.

    `path` is docs/<path>.toml, the file that holds the nav of the site.
    """
    path = root / release.settings_file
    config = SiteConfig(path=path, name=release.settings_file, found=path.is_file())
    config.docs_dir = release.docs_dir
    config.registry = registry
    config.release = release.path
    try:
        project = releases.release_project(root, registry, release.path)
    except releases.RegistryError as exc:
        config.error = "; ".join(exc.problems)
        return config
    config.portal_url = project["extra"]["portal"]["root_url"]
    return apply_project(config, project)


#: Addresses the portal had before OzarLand Academy. A page never links to
#: them: their sites only redirect to the portal.
FORMER_ADDRESSES = ("https://ozarland.github.io/kolla-ansible-academy/",)


def bare_address(address: str) -> str:
    """`address` without its scheme, ending with "/"."""
    return re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", address.strip()).rstrip("/") + "/"


def portal_addresses(root: Path) -> tuple[str, list[str]]:
    """(current address of the portal root, every address of the portal).

    The current one is https://<SITE_DOMAIN>/ or `site_url` of
    zensical.base.toml (releases.portal_root_url); the others are that
    `site_url` and the former addresses. Raises RegistryError.
    """
    base = releases.load_project(root / releases.BASE_CONFIG)
    current = releases.portal_root_url(base)
    known = [current, str(base.get("site_url", "")), *FORMER_ADDRESSES]
    result: list[str] = []
    for address in known:
        if address and bare_address(address) not in result:
            result.append(bare_address(address))
    return current, result


def apply_project(config: SiteConfig, project: dict) -> SiteConfig:
    for key in ("docs_dir", "site_dir", "site_url", "repo_url"):
        value = project.get(key)
        if isinstance(value, str) and value:
            setattr(config, key, value.strip("/") if key.endswith("_dir") else value)
    if isinstance(project.get("use_directory_urls"), bool):
        config.use_directory_urls = project["use_directory_urls"]
    if isinstance(project.get("nav"), list):
        config.nav = project["nav"]
    for key, attr in (("exclude_docs", "exclude"), ("not_in_nav", "not_in_nav")):
        value = project.get(key)
        if isinstance(value, str):
            setattr(config, attr, PatternSet(value))
    return config


def flatten_nav(nav: object) -> tuple[list[str], list[str]]:
    """Return (page paths, problems) of a nav tree.

    A nav item is a path, or a one-key table `{ "Title" = <path or list> }`.
    External URLs are not pages and are left out.
    """
    entries: list[str] = []
    problems: list[str] = []

    def walk(item: object) -> None:
        if isinstance(item, str):
            if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", item) and not item.startswith("//"):
                entries.append(item)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)
        else:
            problems.append(f"nav item {item!r} is neither a path, a list nor a table")

    walk(nav)
    return entries, problems


def list_markdown(root: Path, docs_dir: str) -> list[str]:
    """Markdown files under the docs directory, as sorted docs-relative paths."""
    docs = root / docs_dir
    found = []
    for directory, dirnames, filenames in os.walk(docs):
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNED_DIRS)
        for name in filenames:
            if name.endswith(".md"):
                found.append(Path(directory, name).relative_to(docs).as_posix())
    return sorted(found)


def list_pages(root: Path, config: SiteConfig, docs_dir: str | None = None) -> list[str]:
    """Docs-relative paths of the Markdown files the site builds as pages."""
    docs_dir = docs_dir or config.docs_dir
    return [rel for rel in list_markdown(root, docs_dir) if not config.exclude.match(rel)]


# --- GitHub heading anchors -----------------------------------------------

_SLUG_DROP = re.compile(r"[^\w\- ]", re.UNICODE)


def gh_slug(text: str) -> str:
    """GitHub anchor of a heading text, without the suffix of repeated headings.

    Lowercase, drop every character that is not a word character, a hyphen or
    a space, then turn each space into a hyphen. Hyphens are not collapsed.
    """
    text = unicodedata.normalize("NFC", text).strip().lower()
    return _SLUG_DROP.sub("", text).replace(" ", "-")


class GithubSlugger:
    """Anchors of one document: a repeated heading gets `-1`, `-2`, ..."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def slug(self, text: str) -> str:
        base = gh_slug(text)
        result = base
        while result in self._seen:
            self._seen[base] = self._seen.get(base, 0) + 1
            result = f"{base}-{self._seen[base]}"
        self._seen[result] = 0
        return result


_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_IMAGE = re.compile(r"!\[((?:[^\[\]\\]|\\.)*)\]\((?:[^()\\]|\\.|\([^()]*\))*\)")
_LINK = re.compile(r"\[((?:[^\[\]\\]|\\.)*)\]\((?:[^()\\]|\\.|\([^()]*\))*\)")
_REF_LINK = re.compile(r"\[((?:[^\[\]\\]|\\.)*)\]\[[^\[\]]*\]")
_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]*:[^<>\s]*)>")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG = re.compile(r"</?[A-Za-z][^<>]*>")
_UNDERSCORE_EMPHASIS = re.compile(r"(?<![\w\\])(_{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")


def inline_text(source: str) -> str:
    """Text a reader sees for one line of inline Markdown (used for headings).

    Code spans keep their content, links keep their text, HTML tags and
    emphasis markers disappear, entities and backslash escapes are resolved.
    """
    spans: list[str] = []

    def stash(code: str) -> str:
        if len(code) > 1 and code[0] == code[-1] == " " and code.strip():
            code = code[1:-1]
        spans.append(code)
        return f"\x00{len(spans) - 1}\x00"

    out = []
    i = 0
    while i < len(source):
        char = source[i]
        if char == "\\" and i + 1 < len(source):
            out.append(source[i : i + 2])
            i += 2
        elif char == "`":
            j = i
            while j < len(source) and source[j] == "`":
                j += 1
            width = j - i
            close = _find_backticks(source, j, len(source), width)
            if close == -1:
                out.append(source[i:j])
                i = j
            else:
                out.append(stash(source[j:close]))
                i = close + width
        else:
            out.append(char)
            i += 1
    text = "".join(out)

    text = _IMAGE.sub("", text)
    previous = None
    while previous != text:  # nested brackets resolve from the inside out
        previous = text
        text = _LINK.sub(r"\1", text)
        text = _REF_LINK.sub(r"\1", text)
    text = _AUTOLINK.sub(r"\1", text)
    text = _HTML_COMMENT.sub("", text)
    text = _HTML_TAG.sub("", text)
    previous = None
    while previous != text:
        previous = text
        text = _UNDERSCORE_EMPHASIS.sub(r"\2", text)
    text = _ESCAPE.sub(r"\1", text)
    text = html.unescape(text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    return " ".join(text.split())


def _find_backticks(text: str, start: int, end: int, width: int) -> int:
    """Offset of the next run of exactly `width` backticks in text[start:end]."""
    i = start
    while i < end:
        if text[i] == "`":
            j = i
            while j < end and text[j] == "`":
                j += 1
            if j - i == width:
                return i
            i = j
        else:
            i += 1
    return -1


# --- front matter ----------------------------------------------------------

_KEY = re.compile(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$")
_BLOCK_SCALAR = re.compile(r"^[|>][+-]?$")
# A plain (unquoted) YAML scalar cannot start with one of these.
_PLAIN_FORBIDDEN_START = tuple("[]{}*&!|>'\"%@`,#")


class FrontMatterError(Exception):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.message = message


def _scalar(raw: str, line: int, key: str) -> str:
    """Value of a one-line YAML scalar (plain, single- or double-quoted)."""
    raw = raw.strip()
    if raw[:1] == "'":
        match = re.match(r"^'((?:[^']|'')*)'[ \t]*(?:#.*)?$", raw)
        if not match:
            raise FrontMatterError(line, f"`{key}`: single-quoted value is not closed")
        return match.group(1).replace("''", "'")
    if raw[:1] == '"':
        match = re.match(r'^"((?:[^"\\]|\\.)*)"[ \t]*(?:#.*)?$', raw)
        if not match:
            raise FrontMatterError(line, f"`{key}`: double-quoted value is not closed")
        return re.sub(
            r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), match.group(1)
        )
    if raw.startswith(_PLAIN_FORBIDDEN_START):
        raise FrontMatterError(line, f"`{key}`: value starts with `{raw[0]}` and must be quoted")
    if re.search(r":(\s|$)", raw):
        raise FrontMatterError(
            line, f"`{key}`: value contains `: ` and must be quoted (YAML reads it as a nested key)"
        )
    if re.search(r"\s#", raw):
        raise FrontMatterError(
            line, f"`{key}`: value contains ` #` and must be quoted (YAML reads the rest as a comment)"
        )
    return raw


def _flow_list(raw: str, line: int, key: str) -> list[str]:
    """Items of a YAML flow sequence `[a, "b, c", d]`."""
    match = re.match(r"^\[(.*)\][ \t]*(?:#.*)?$", raw.strip(), re.DOTALL)
    if not match:
        raise FrontMatterError(line, f"`{key}`: list is not closed with `]`")
    items = []
    for part in re.findall(r"""\s*("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,]*)\s*(?:,|$)""", match.group(1)):
        part = part.strip()
        if part:
            items.append(_scalar(part, line, key))
    return items


def parse_front_matter(text: str) -> tuple[dict[str, object], dict[str, int], int]:
    """Parse the front matter of a page.

    Returns (values, line of each key, number of lines of the block). Only the
    subset the portal uses is understood: top-level keys with a scalar, a list
    (flow or block) or a block scalar. Nested tables are kept as text.
    Raises FrontMatterError when the block is missing or cannot be read.
    """
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        raise FrontMatterError(1, "file does not start with a `---` front matter block")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), None)
    if end is None:
        raise FrontMatterError(1, "front matter block is not closed with `---`")

    values: dict[str, object] = {}
    where: dict[str, int] = {}
    i = 1
    while i < end:
        line = lines[i]
        number = i + 1
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        match = _KEY.match(line)
        if not match:
            raise FrontMatterError(number, f"line is not `key: value`: {line.strip()!r}")
        key, raw = match.group(1), (match.group(2) or "").strip()
        if key in values:
            raise FrontMatterError(number, f"`{key}` is defined twice")
        # Indented lines that follow belong to this key.
        block = []
        i += 1
        while i < end and (
            not lines[i].strip()
            or lines[i][:1] in (" ", "\t")
            or (not raw and lines[i].startswith("- "))
        ):
            block.append(lines[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        where[key] = number

        if raw.startswith("#"):
            raw = ""
        if raw.startswith("{"):
            values[key] = raw  # inline table: not interpreted
        elif raw.startswith("["):
            values[key] = _flow_list(" ".join([raw, *(b.strip() for b in block)]), number, key)
        elif _BLOCK_SCALAR.match(raw):
            joiner = "\n" if raw[0] == "|" else " "
            values[key] = joiner.join(b.strip() for b in block).strip()
        elif raw:
            if block:  # plain scalar continued on the next lines
                raw = " ".join([raw, *(b.strip() for b in block if b.strip())])
            values[key] = _scalar(raw, number, key)
        elif block and all(b.lstrip().startswith("- ") or not b.strip() for b in block):
            values[key] = [
                _scalar(b.lstrip()[2:], number, key) for b in block if b.strip()
            ]
        elif block:
            values[key] = "\n".join(block)  # nested table: not interpreted
        else:
            values[key] = None
    return values, where, end + 1


# --- Markdown documents ----------------------------------------------------

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_QUOTE_PREFIX = re.compile(r"^(?:[ ]{0,3}>[ ]?)+")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)(.*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_BLOCK_START = re.compile(r"^[ \t]*(?:[-*+][ \t]|\d+[.)][ \t]|#{1,6}(?:[ \t]|$)|\|)")
_ID_ATTR = re.compile(
    r"""<[A-Za-z][\w:-]*\b[^<>]*?\sid\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE
)
_NAME_ATTR = re.compile(r"""<a\b[^<>]*?\sname\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_HREF_ATTR = re.compile(
    r"""<(?:a|area)\b[^<>]*?\shref\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE
)
_SRC_ATTR = re.compile(
    r"""<(?:img|source|video|audio)\b[^<>]*?\ssrc\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE
)
_REF_DEFINITION = re.compile(
    r"""^[ ]{0,3}\[(?!\^)((?:[^\[\]\\]|\\.)+)\]:[ \t]*(<[^<>\n]*>|[^\s<]\S*)"""
    r"""(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*$""",
    re.MULTILINE,
)
_REF_USE = re.compile(r"\]\[((?:[^\[\]\\]|\\.)+)\]")
_TODO = re.compile(r"<!--\s*TODO editorial")
_ALERT = re.compile(r"^ {0,3}(?:>[ ]?)+\[!([^\]]*)\](.*)$")
_QUOTE_LINE = re.compile(r"^ {0,3}>")
_ADMONITION = re.compile(r"^[ \t]*(!!!|\?\?\?\+?)[ \t]+\w")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# Text in brackets that is an evidence label, not a link label.
_EVIDENCE_LABELS = {"code", "not available"}


#: Fillers that replace code spans and HTML comments before links are read.
_CODE_FILL = "\x01"
_COMMENT_FILL = "\x02"


def _blank(text: str, fill: str) -> str:
    """Same length and line breaks, every other character replaced."""
    return re.sub(r"[^\n]", fill, text)


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


@dataclass
class Link:
    line: int
    target: str
    kind: str  # "link", "image", "definition", "html"


class Document:
    """One Markdown file: front matter, headings, anchors, fences and links."""

    def __init__(self, path: Path, rel: str) -> None:
        self.path = path
        self.rel = rel  # repository-relative, posix
        data = path.read_bytes()
        try:
            self.text = data.decode("utf-8-sig")
            self.encoding_error = False
        except UnicodeDecodeError:
            self.text = data.decode("utf-8-sig", errors="replace")
            self.encoding_error = True
        self.lines = self.text.split("\n")

        self.front: dict[str, object] | None = None
        self.front_lines: dict[str, int] = {}
        self.front_error: FrontMatterError | None = None
        body_start = 0
        try:
            self.front, self.front_lines, body_start = parse_front_matter(self.text)
        except FrontMatterError as exc:
            self.front_error = exc
            # Skip an unreadable block so that its lines are not read as Markdown.
            if self.lines and self.lines[0].rstrip() == "---":
                end = next(
                    (i for i in range(1, len(self.lines)) if self.lines[i].rstrip() in ("---", "...")),
                    None,
                )
                body_start = end + 1 if end is not None else 0

        self.fences: list[tuple[int, str]] = []  # (line, info string)
        self.unclosed_fence: int | None = None
        self.headings: list[tuple[int, int, str, str]] = []  # (line, level, text, anchor)
        self.callouts: list[tuple[int, str, str, bool]] = []  # (line, type, rest, first line)
        self.admonitions: list[int] = []
        self._scan_blocks(body_start)

        masked = self._mask_inline_code(self._masked_lines)
        self.todo_lines = [masked.count("\n", 0, m.start()) + 1 for m in _TODO.finditer(masked)]
        masked = _HTML_COMMENT.sub(lambda m: _blank(m.group(0), _COMMENT_FILL), masked)
        self.masked = masked
        self.masked_lines = masked.split("\n")

        self.explicit_ids: list[tuple[int, str]] = []
        for regex in (_ID_ATTR, _NAME_ATTR):
            for match in regex.finditer(masked):
                value = match.group(1) if match.group(1) is not None else match.group(2)
                self.explicit_ids.append((self._line(match.start()), html.unescape(value)))
        self.anchors = {anchor for _, _, _, anchor in self.headings if anchor}
        self.anchors.update(value for _, value in self.explicit_ids)

        self.definitions: dict[str, int] = {}
        self.links: list[Link] = []
        self.reference_uses: list[tuple[int, str]] = []
        self._scan_links()

    # -- block structure ----------------------------------------------------

    def _scan_blocks(self, body_start: int) -> None:
        slugger = GithubSlugger()
        masked: list[str] = []
        fence: tuple[str, int] | None = None
        fence_line = 0
        previous = ""  # previous line outside fences, for setext headings
        previous_quoted = False

        for index, line in enumerate(self.lines):
            number = index + 1
            if index < body_start:
                masked.append("")
                continue
            content = _QUOTE_PREFIX.sub("", line)
            match = _FENCE.match(content)
            if fence is not None:
                masked.append("")
                if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1]:
                    if not match.group(2).strip():
                        fence = None
                continue
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)))
                fence_line = number
                self.fences.append((number, match.group(2).strip()))
                masked.append("")
                previous = ""
                previous_quoted = False
                continue

            masked.append(line)
            alert = _ALERT.match(line)
            if alert:
                self.callouts.append((number, alert.group(1), alert.group(2), not previous_quoted))
            if _ADMONITION.match(line):
                self.admonitions.append(number)

            atx = _ATX.match(content)
            setext = _SETEXT.match(content)
            if atx:
                text = re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", atx.group(2).strip()).strip()
                text = inline_text(text)
                self.headings.append((number, len(atx.group(1)), text, slugger.slug(text)))
            elif (
                setext
                and previous.strip()
                and not previous[:1].isspace()
                and not _BLOCK_START.match(previous)
                and not previous.startswith(("<", "|"))
            ):
                text = inline_text(previous.strip())
                level = 1 if setext.group(1)[0] == "=" else 2
                self.headings.append((number - 1, level, text, slugger.slug(text)))
            previous = "" if (atx or setext) else content
            previous_quoted = bool(_QUOTE_LINE.match(line))

        if fence is not None:
            self.unclosed_fence = fence_line
        self._masked_lines = masked

    @staticmethod
    def _mask_inline_code(lines: list[str]) -> str:
        """Blank the code spans. A span cannot leave its block."""
        text = "\n".join(lines)
        chars = list(text)
        # Block boundaries: blank lines, list items, headings and table rows.
        starts = [0]
        offset = 0
        for index, line in enumerate(lines):
            if index and (not line.strip() or not lines[index - 1].strip() or _BLOCK_START.match(line)):
                starts.append(offset)
            offset += len(line) + 1
        starts.append(len(text))

        for start, end in zip(starts, starts[1:]):
            i = start
            while i < end:
                if text[i] == "\\":
                    i += 2
                elif text[i] == "`":
                    j = i
                    while j < end and text[j] == "`":
                        j += 1
                    close = _find_backticks(text, j, end, j - i)
                    if close == -1:
                        i = j
                    else:
                        stop = close + (j - i)
                        for position in range(i, stop):
                            if chars[position] != "\n":
                                chars[position] = _CODE_FILL
                        i = stop
                else:
                    i += 1
        return "".join(chars)

    def _line(self, offset: int) -> int:
        return self.masked.count("\n", 0, offset) + 1

    # -- links ----------------------------------------------------------------

    def _scan_links(self) -> None:
        text = self.masked
        for match in _REF_DEFINITION.finditer(text):
            target = match.group(2)
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            self.definitions.setdefault(_normalize_label(match.group(1)), self._line(match.start()))
            self.links.append(Link(self._line(match.start()), _ESCAPE.sub(r"\1", target), "definition"))

        for match in re.finditer(r"\]\(", text):
            close = match.start()
            if self._escaped(close):
                continue
            opening = self._opening_bracket(close)
            if opening == -1:
                continue
            target = self._destination(match.end())
            if target is None:
                continue
            kind = "image" if opening and text[opening - 1] == "!" else "link"
            self.links.append(Link(self._line(match.end()), _ESCAPE.sub(r"\1", target), kind))

        for regex in (_HREF_ATTR, _SRC_ATTR):
            for match in regex.finditer(text):
                value = match.group(1) if match.group(1) is not None else match.group(2)
                self.links.append(Link(self._line(match.start()), html.unescape(value).strip(), "html"))

        for match in _REF_USE.finditer(text):
            if self._escaped(match.start()) or text.startswith("(", match.end()):
                continue
            opening = self._opening_bracket(match.start())
            if opening == -1:
                continue
            label = _normalize_label(match.group(1))
            if label.startswith("^") or label in _EVIDENCE_LABELS:
                continue
            self.reference_uses.append((self._line(match.start()), match.group(1)))
        self.links.sort(key=lambda link: link.line)

    def _escaped(self, offset: int) -> bool:
        backslashes = 0
        while offset - backslashes - 1 >= 0 and self.masked[offset - backslashes - 1] == "\\":
            backslashes += 1
        return backslashes % 2 == 1

    def _opening_bracket(self, close: int) -> int:
        """Offset of the `[` that matches the `]` at `close` (-1: none)."""
        text = self.masked
        depth = 0
        i = close - 1
        while i >= 0:
            char = text[i]
            if char == "\n" and i and text[i - 1] == "\n":
                return -1
            if char in "[]" and not self._escaped(i):
                if char == "]":
                    depth += 1
                elif depth == 0:
                    return i
                else:
                    depth -= 1
            i -= 1
        return -1

    def _destination(self, start: int) -> str | None:
        """Destination of an inline link whose `(` ends at `start` (None: not a link)."""
        text = self.masked
        size = len(text)

        def skip_space(i: int) -> int:
            newlines = 0
            while i < size and text[i] in " \t\n":
                newlines += text[i] == "\n"
                if newlines > 1:
                    break
                i += 1
            return i

        i = skip_space(start)
        if i < size and text[i] == "<":
            end = text.find(">", i)
            if end == -1 or "\n" in text[i:end]:
                return None
            target = text[i + 1 : end]
            i = end + 1
        else:
            depth = 0
            begin = i
            while i < size:
                char = text[i]
                if char == "\\" and i + 1 < size:
                    i += 2
                    continue
                if char in " \t\n":
                    break
                if char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        break
                    depth -= 1
                i += 1
            target = text[begin:i]
        i = skip_space(i)
        if i < size and text[i] in "\"'(":
            closer = ")" if text[i] == "(" else text[i]
            end = text.find(closer, i + 1)
            if end == -1 or "\n\n" in text[i:end]:
                return None
            i = skip_space(end + 1)
        if i < size and text[i] == ")":
            return target
        return None


# --- the checks ------------------------------------------------------------


class Checker:
    def __init__(self, root: Path, config: SiteConfig, docs_dir: str, report: Report) -> None:
        self.root = root
        self.config = config
        self.docs_dir = docs_dir
        self.report = report
        self._documents: dict[str, Document] = {}
        self.files: set[str] = set()
        self.dirs: set[str] = set()
        for directory, dirnames, filenames in os.walk(root):
            base = Path(directory).relative_to(root).as_posix()
            base = "" if base == "." else base + "/"
            # The built site is not a link target (only the top-level one:
            # tools/site is a source directory).
            dirnames[:] = [
                d for d in dirnames if d not in PRUNED_DIRS and base + d != releases.SITE_DIR
            ]
            self.dirs.update(base + d for d in dirnames)
            self.files.update(base + f for f in filenames)
        self.stats = {
            "pages": 0,
            "other files": 0,
            "relative links": 0,
            "links with a fragment": 0,
            "external links": 0,
            "code blocks": 0,
            "callouts": 0,
            "headings": 0,
        }
        self.languages: dict[str, int] = {}

    def document(self, rel: str) -> Document:
        if rel not in self._documents:
            self._documents[rel] = Document(self.root / rel, rel)
        return self._documents[rel]

    # -- one page -------------------------------------------------------------

    def check_page(self, rel: str) -> None:
        doc = self.document(rel)
        self.stats["pages"] += 1
        if doc.encoding_error:
            self.report.error(rel, 1, "encoding", "file is not valid UTF-8")
        self._front_matter(doc)
        self._fences(doc)
        self._callouts(doc)
        self._removed_paths(doc)
        for line in doc.todo_lines:
            self.report.warning(rel, line, "todo-editorial", "leftover `<!-- TODO editorial` marker")
        self._site_addresses(doc, in_docs=True)
        self._links(doc, in_docs=True)

    def check_extra(self, rel: str) -> None:
        """Markdown outside docs/ (README.md ...): links only."""
        doc = self.document(rel)
        self.stats["other files"] += 1
        if doc.unclosed_fence:
            self.report.error(rel, doc.unclosed_fence, "code-language", "code fence is never closed")
        self._site_addresses(doc, in_docs=False)
        self._links(doc, in_docs=False)

    def _site_addresses(self, doc: Document, in_docs: bool) -> None:
        """No address of the portal written in full (links, autolinks, plain text).

        Code is not looked at: a command may name an address.
        """
        addresses = self.config.addresses
        if not addresses:
            return
        current = bare_address(self.config.portal_url) if self.config.portal_url else ""
        pattern = re.compile(
            r"(?<![\w.-])(?:[A-Za-z]+://)?(" + "|".join(re.escape(a.rstrip("/")) for a in addresses) + r")(?=[/\s)>\]\"'#?]|$)"
        )
        for match in pattern.finditer(doc.masked):
            found = match.group(1) + "/"
            line = doc._line(match.start())
            if in_docs:
                self.report.error(
                    doc.rel,
                    line,
                    "link-site-address",
                    f"`{match.group(0)}` is an address of the portal: use a relative link, so that the site works "
                    "at any address (to another site: ../<path>/ relative to this file)",
                )
            elif found != current:
                self.report.error(
                    doc.rel,
                    line,
                    "link-site-address",
                    f"`{match.group(0)}` is not the current address of the portal (https://{current}): "
                    "write the current one",
                )

    def _front_matter(self, doc: Document) -> None:
        error, warning = self.report.error, self.report.warning
        if doc.front_error is not None:
            error(doc.rel, doc.front_error.line, "front-matter", doc.front_error.message)
            return
        front = doc.front or {}
        lines = doc.front_lines

        title = front.get("title")
        if not isinstance(title, str) or not title.strip():
            error(doc.rel, lines.get("title", 1), "title", "front matter has no `title`")

        description = front.get("description")
        if "description" not in front:
            warning(doc.rel, 1, "description", "front matter has no `description`")
        elif not isinstance(description, str) or not description.strip():
            error(doc.rel, lines["description"], "description", "`description` is empty or not a text")
        elif len(description) > DESCRIPTION_MAX:
            error(
                doc.rel,
                lines["description"],
                "description",
                f"`description` has {len(description)} characters (maximum {DESCRIPTION_MAX})",
            )

        if "impact" in front:
            impact = front["impact"]
            values = [impact] if isinstance(impact, str) else impact
            if not isinstance(values, list):
                error(doc.rel, lines["impact"], "impact", "`impact` is not a list")
            else:
                for value in values:
                    if value not in IMPACT_VOCABULARY:
                        hint = difflib.get_close_matches(str(value), IMPACT_VOCABULARY, 1)
                        error(
                            doc.rel,
                            lines["impact"],
                            "impact",
                            f"`{value}` is not an impact value"
                            + (f" (did you mean `{hint[0]}`?)" if hint else "")
                            + "; allowed: "
                            + ", ".join(IMPACT_VOCABULARY),
                        )

        if "tags" in front:
            tags = front["tags"]
            if not isinstance(tags, list):
                warning(doc.rel, lines["tags"], "tags", "`tags` is not a list")
            else:
                for tag in tags:
                    if tag != tag.lower() or not tag.strip():
                        warning(doc.rel, lines["tags"], "tags", f"tag `{tag}` is not lowercase")

    def _fences(self, doc: Document) -> None:
        for line, info in doc.fences:
            self.stats["code blocks"] += 1
            language = info.strip("{}. \t").split()[0] if info.strip("{}. \t") else ""
            if not language:
                self.report.error(
                    doc.rel, line, "code-language", "fenced code block has no language (use `text` for plain output)"
                )
            else:
                self.languages[language] = self.languages.get(language, 0) + 1
        if doc.unclosed_fence:
            self.report.error(doc.rel, doc.unclosed_fence, "code-language", "code fence is never closed")

    def _callouts(self, doc: Document) -> None:
        allowed = ", ".join(f"[!{t}]" for t in ALERT_TYPES)
        for line, kind, rest, first in doc.callouts:
            self.stats["callouts"] += 1
            if kind not in ALERT_TYPES:
                self.report.error(
                    doc.rel, line, "callout", f"`[!{kind}]` is not a GitHub alert type; allowed: {allowed}"
                )
            elif rest.strip():
                self.report.error(
                    doc.rel, line, "callout", f"`[!{kind}]` must be alone on its line (found {rest.strip()!r} after it)"
                )
            elif not first:
                self.report.error(
                    doc.rel, line, "callout", f"`[!{kind}]` must be the first line of its blockquote"
                )
        for line in doc.admonitions:
            self.report.error(
                doc.rel, line, "callout", f"`!!!` / `???` blocks do not render on github.com; use {allowed}"
            )

    def _removed_paths(self, doc: Document) -> None:
        """Old paths anywhere in the file, code blocks included.

        Inside an HTML comment (a note left by the migration, invisible to the
        reader) the reference is a warning until --strict.
        """
        for index, line in enumerate(doc.lines):
            for regex, label in REMOVED_PATHS:
                match = regex.search(line)
                if not match:
                    continue
                masked = doc.masked_lines[index] if index < len(doc.masked_lines) else ""
                in_comment = len(masked) == len(line) and masked[match.start()] == _COMMENT_FILL
                excerpt = line[match.start() : match.start() + 60].strip()
                if in_comment:
                    self.report.warning(
                        doc.rel,
                        index + 1,
                        "removed-path",
                        f"HTML comment refers to {label} of the old layout: `{excerpt}`",
                    )
                else:
                    self.report.error(
                        doc.rel, index + 1, "removed-path", f"reference to {label} of the old layout: `{excerpt}`"
                    )
                break

    # -- links ------------------------------------------------------------------

    def _links(self, doc: Document, in_docs: bool) -> None:
        for line, label in doc.reference_uses:
            if _normalize_label(label) not in doc.definitions:
                self.report.error(
                    doc.rel, line, "link-reference", f"`[...][{label}]` uses a label that is not defined in this file"
                )
        for link in doc.links:
            self._link(doc, link, in_docs)

    def _link(self, doc: Document, link: Link, in_docs: bool) -> None:
        error = self.report.error
        target = link.target.strip()
        docs_prefix = self.docs_dir + "/"
        if not target:
            error(doc.rel, link.line, "link-file", "link has an empty target")
            return

        if _SCHEME.match(target) or target.startswith("//"):
            self.stats["external links"] += 1
            self._absolute(doc, link, target, in_docs)
            return
        if target.startswith("/"):
            error(
                doc.rel,
                link.line,
                "link-style",
                f"`{target}` is an absolute path; use a relative link (it would not resolve on the site)",
            )
            return

        path, _, fragment = target.partition("#")
        path = unquote(path.partition("?")[0])
        fragment = unquote(fragment)
        self.stats["relative links"] += 1

        if not path:
            resolved = doc.rel
        else:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(doc.rel), path))
            if resolved == ".." or resolved.startswith("../"):
                error(doc.rel, link.line, "link-file", f"`{path}` points outside the repository")
                return
            if in_docs and path.endswith("/") and self.config.registry is not None:
                self._site_link(doc, link, resolved, fragment)
                return
            if resolved in self.dirs or resolved == ".":
                if in_docs or "#" in target:
                    error(
                        doc.rel,
                        link.line,
                        "link-style",
                        f"`{path}` is a directory; link to a file (for a section, its index.md)",
                    )
                return
            if resolved not in self.files:
                error(doc.rel, link.line, "link-file", f"`{path}` does not exist" + self._file_hint(resolved))
                return
            other = self._site_of(resolved) if in_docs else None
            if other is not None and other.path != self.config.release:
                error(
                    doc.rel,
                    link.line,
                    "link-site",
                    f"`{path}` is a file of another site ({other.docs_dir}/): link to its page with an address "
                    f"relative to this file, {self._site_address(doc.rel, other, resolved)}",
                )
                return
            if in_docs and not resolved.startswith(docs_prefix):
                error(
                    doc.rel,
                    link.line,
                    "link-style",
                    f"`{path}` is outside {docs_prefix} and is not part of the site; "
                    "use an absolute https://github.com/... link",
                )
                return

        if "#" not in target:
            return
        self.stats["links with a fragment"] += 1
        if not resolved.endswith(".md"):
            error(
                doc.rel,
                link.line,
                "link-anchor",
                f"`{target}`: a fragment can only be checked on a Markdown target",
            )
            return
        if not fragment:
            error(doc.rel, link.line, "link-anchor", f"`{target}` has an empty fragment")
            return
        anchors = self.document(resolved).anchors
        if fragment not in anchors:
            where = "this file" if resolved == doc.rel else resolved
            error(
                doc.rel,
                link.line,
                "link-anchor",
                f"`#{fragment}` is not an anchor of {where}" + self._anchor_hint(fragment, anchors),
            )

    def _absolute(self, doc: Document, link: Link, target: str, in_docs: bool) -> None:
        """Absolute URL: allowed, unless it is an internal link in disguise.

        An address of the portal is reported by _site_addresses.
        """
        if any(bare_address(target).startswith(a) for a in self.config.addresses):
            return
        repo_url = self.config.repo_url.rstrip("/")
        if not repo_url or not target.startswith(repo_url + "/"):
            return
        match = re.match(r"^(?:blob|tree|raw)/([^/]+)/([^#?]*)", target[len(repo_url) + 1 :])
        if not match:
            return
        branch, path = match.group(1), unquote(match.group(2)).rstrip("/")
        if in_docs and (path == self.docs_dir or path.startswith(self.docs_dir + "/")):
            self.report.error(
                doc.rel,
                link.line,
                "link-style",
                f"`{target}` points to a page of the portal; use a relative link to the .md file",
            )
        elif branch == "main" and path and path not in self.files and path not in self.dirs:
            self.report.error(
                doc.rel,
                link.line,
                "link-repo-file",
                f"`{target}`: `{path}` does not exist in the repository",
            )

    def _site_of(self, resolved: str) -> releases.Release | None:
        """Available or planned site whose docs directory holds the repository path `resolved`."""
        registry = self.config.registry
        if registry is None:
            return None
        found = None
        for release in registry.releases:
            if resolved == release.docs_dir or resolved.startswith(release.docs_dir + "/"):
                if found is None or len(release.docs_dir) > len(found.docs_dir):
                    found = release
        return found

    def _site_address(self, source: str, release: releases.Release, resolved: str) -> str:
        """Address of the page of `resolved` (a file of `release`), relative to the file `source`."""
        rel = Path(resolved[len(release.docs_dir) + 1 :])
        page = rel.as_posix() if rel.suffix != ".md" else releases.page_url(rel)
        target = f"{release.docs_dir}/{page}"
        address = posixpath.relpath(target, posixpath.dirname(source))
        return address + ("/" if page.endswith("/") or not page else "")

    def _site_link(self, doc: Document, link: Link, resolved: str, fragment: str) -> None:
        """A link written as a page address ("…/"): it must reach a page of another site.

        Each site is built on its own, so a link to another one cannot name its
        .md file; Zensical keeps a relative address and adjusts it to the
        published page. The address is relative to the file, as a link to a
        .md file is.
        """
        error = self.report.error
        registry = self.config.registry
        target = link.target
        # The root of the portal and the home of a versioned module are pages of the root site.
        if resolved == releases.DOCS_ROOT or any(
            m.versioned and resolved == m.docs_dir for m in registry.modules
        ):
            if fragment:
                error(doc.rel, link.line, "link-site", f"`{target}`: a fragment cannot be checked on a page of the root site")
            return
        site = self._site_of(resolved)
        if site is None:
            error(doc.rel, link.line, "link-file", f"`{target}` is not a page of the portal (it does not lead into a site of {releases.REGISTRY_FILE})")
            return
        if site.path == self.config.release:
            inner = resolved[len(site.docs_dir) + 1 :] if resolved != site.docs_dir else ""
            error(
                doc.rel,
                link.line,
                "link-style",
                f"`{target}` is a page of this site: link to its .md file "
                f"({(inner + '/index.md') if inner else 'index.md'} or {inner}.md, relative to this file)",
            )
            return
        inner = resolved[len(site.docs_dir) + 1 :] if resolved != site.docs_dir else ""
        if not site.available:
            if inner:
                error(doc.rel, link.line, "link-site", f"`{target}`: `{site.path}` is planned and has no page other than its home")
            elif fragment:
                error(doc.rel, link.line, "link-site", f"`{target}`: `{site.path}` is planned, its page has no anchors to link to")
            return
        candidates = [f"{inner}/index.md", f"{inner}.md"] if inner else ["index.md"]
        source = next((f"{site.docs_dir}/{c}" for c in candidates if f"{site.docs_dir}/{c}" in self.files), None)
        if source is None:
            error(
                doc.rel,
                link.line,
                "link-site",
                f"`{target}`: `{site.path}` has no page `{inner or 'index'}` "
                f"(no {' or '.join(candidates)} under {site.docs_dir}/)",
            )
            return
        if fragment:
            self.stats["links with a fragment"] += 1
            if fragment not in self.document(source).anchors:
                error(doc.rel, link.line, "link-anchor", f"`{target}`: `#{fragment}` is not an anchor of {source}")

    def _file_hint(self, resolved: str) -> str:
        name = posixpath.basename(resolved)
        same_name = sorted(f for f in self.files if posixpath.basename(f) == name)
        if same_name:
            return f" (a file with this name exists: {', '.join(same_name[:3])})"
        folded = resolved.casefold()
        other_case = [f for f in self.files if f.casefold() == folded]
        if other_case:
            return f" (case differs: {other_case[0]})"
        return ""

    @staticmethod
    def _anchor_hint(fragment: str, anchors: set[str]) -> str:
        lowered = [a for a in anchors if a.lower() == fragment.lower()]
        close = lowered or difflib.get_close_matches(fragment, sorted(anchors), 1, 0.6)
        return f" (closest: `#{close[0]}`)" if close else ""

    # -- nav --------------------------------------------------------------------

    def check_nav(self, pages: list[str]) -> None:
        config = self.config
        name = config.name or config.path.name
        error = self.report.error
        if not config.found:
            error(name, 1, "config", f"{name} does not exist: the nav cannot be checked")
            return
        if config.error:
            error(name, 1, "config", f"cannot be read: {config.error}")
            return
        if config.nav is None:
            error(name, 1, "nav", "`project.nav` is not defined: every page must be listed in the nav")
            return
        entries, problems = flatten_nav(config.nav)
        for problem in problems:
            error(name, 1, "nav", problem)
        config_lines = config.path.read_text(encoding="utf-8").split("\n")

        def line_of(entry: str, occurrence: int = 1) -> int:
            """Line of the n-th quoted occurrence of a nav entry in the file."""
            for number, text in enumerate(config_lines, 1):
                if f'"{entry}"' in text or f"'{entry}'" in text:
                    occurrence -= 1
                    if occurrence == 0:
                        return number
            return 1

        docs_prefix = self.docs_dir + "/"
        seen: dict[str, int] = {}
        for entry in entries:
            normalized = posixpath.normpath(entry)
            seen[normalized] = seen.get(normalized, 0) + 1
            if seen[normalized] > 1:
                error(name, line_of(entry, seen[normalized]), "nav", f"nav entry `{entry}` is listed twice")
                continue
            if docs_prefix + normalized not in self.files:
                error(name, line_of(entry), "nav", f"nav entry `{entry}` does not exist under {docs_prefix}")
            elif self.config.exclude.match(normalized):
                error(name, line_of(entry), "nav", f"nav entry `{entry}` is excluded by `exclude_docs`")
        for page in pages:
            if page not in seen and not config.not_in_nav.match(page):
                error(docs_prefix + page, 1, "nav", f"page is not listed in the nav of {name}")


# --- report ----------------------------------------------------------------


def print_report(report: Report, summary: str, tool: str = "check_docs", annotate_files: bool = True) -> int:
    """Print findings grouped by file, then the summary. Returns the exit status.

    On GitHub Actions the errors are also printed as annotations; they point
    to the file when `annotate_files` is set (paths of the repository).
    """
    findings = sorted(report.findings, key=lambda f: (f.path, f.line, f.rule, f.message))
    current = None
    for finding in findings:
        if finding.path != current:
            current = finding.path
            print(f"\n{current}")
        print(f"  line {finding.line:<5} {finding.level:<8} {finding.rule:<15} {finding.message}")

    errors, warnings = report.count("error"), report.count("warning")
    if findings:
        by_rule: dict[str, list[int]] = {}
        for finding in findings:
            by_rule.setdefault(finding.rule, [0, 0])[finding.level == "warning"] += 1
        print("\nFindings by rule:")
        for rule in sorted(by_rule):
            counts = by_rule[rule]
            parts = [f"{counts[0]} error(s)"] if counts[0] else []
            parts += [f"{counts[1]} warning(s)"] if counts[1] else []
            print(f"  {rule:<15} {', '.join(parts)}")
        print()
    print(summary)

    if os.environ.get("GITHUB_ACTIONS") == "true":
        for finding in [f for f in findings if f.level == "error"][:50]:
            message = finding.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            if annotate_files:
                where = f"file={finding.path},line={finding.line},"
            else:
                where, message = "", f"{finding.path}:{finding.line}: {message}"
            print(f"::error {where}title={tool} {finding.rule}::{message}")

    if errors:
        print(f"{tool}: FAILED - {errors} error(s), {warnings} warning(s)")
        return 1
    note = " (--strict turns warnings into errors)" if warnings else ""
    print(f"{tool}: OK - 0 errors, {warnings} warning(s){note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Source checks for the Markdown of the portal (no build needed).",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    parser.add_argument(
        "--release", metavar="PATH", help="check this site only, such as day2/2024.1 (default: every available site)"
    )
    parser.add_argument("--strict", action="store_true", help="report warnings as errors")
    parser.add_argument(
        "--extra",
        action="append",
        metavar="FILE",
        help=f"Markdown file outside docs/ whose links are checked (default: {', '.join(EXTRA_FILES)})",
    )
    parser.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    args = parser.parse_args(argv)

    if args.list_rules:
        for rule, text in RULES.items():
            level = "warning" if rule in WARNING_RULES else "error"
            print(f"{rule:<15} {level:<8} {text}")
        print("description     warning  when the key is missing")
        print("removed-path    warning  when the reference is inside an HTML comment")
        print("--strict reports every warning as an error.")
        return 0

    root = args.root.resolve()
    report = Report(strict=args.strict)
    try:
        registry = releases.load_registry(root)
        selected = releases.select(registry, args.release)
    except releases.RegistryError as exc:
        for problem in exc.problems:
            report.error(releases.REGISTRY_FILE, 1, "registry", problem)
        return print_report(report, "The registry cannot be used: nothing else was checked.")
    for problem in releases.layout_problems(root, registry):
        report.error(releases.REGISTRY_FILE, 1, "registry", problem)
    try:
        current_address, addresses = portal_addresses(root)
    except releases.RegistryError as exc:
        for problem in exc.problems:
            report.error(releases.BASE_CONFIG, 1, "config", problem)
        current_address, addresses = "", []

    stats: dict[str, int] = {}
    languages: dict[str, int] = {}
    checked = []
    for release in selected:
        docs_dir = release.docs_dir
        if not (root / docs_dir).is_dir():
            continue  # reported above by the `registry` rule
        config = release_config(root, registry, release)
        config.addresses = addresses
        checker = Checker(root, config, docs_dir, report)
        pages = list_pages(root, config, docs_dir)
        for page in pages:
            checker.check_page(f"{docs_dir}/{page}")
        checker.check_nav(pages)
        checker.stats["headings"] = sum(len(checker.document(f"{docs_dir}/{p}").headings) for p in pages)
        for key, value in checker.stats.items():
            stats[key] = stats.get(key, 0) + value
        for name, count in checker.languages.items():
            languages[name] = languages.get(name, 0) + count
        checked.append(f"{release.path} ({len(pages)})")

    # Files outside docs/: links only, against the shared configuration.
    base = load_config(root / releases.BASE_CONFIG)
    if not base.found or base.error:
        report.error(releases.BASE_CONFIG, 1, "config", base.error or "the file does not exist")
    base.registry = registry
    base.portal_url = current_address
    base.addresses = addresses
    checker = Checker(root, base, releases.DOCS_ROOT, report)
    extras = args.extra if args.extra is not None else [f for f in EXTRA_FILES if (root / f).is_file()]
    for extra in extras:
        if not (root / extra).is_file():
            report.error(extra, 1, "link-file", "file given with --extra does not exist")
            continue
        checker.check_extra(Path(extra).as_posix())
    for key, value in checker.stats.items():
        stats[key] = stats.get(key, 0) + value

    planned = ", ".join(release.path for release in registry.planned) or "none"
    language_list = ", ".join(f"{name} {count}" for name, count in sorted(languages.items()))
    summary = (
        f"Sites checked (pages): {', '.join(checked) or 'none'}. Planned, no content: {planned}.\n"
        f"Address of the portal: {current_address or 'unknown'}\n"
        f"Checked {stats['pages']} page(s) under {releases.DOCS_ROOT}/ and {stats['other files']} other Markdown file(s): "
        f"{stats['headings']} headings, {stats['relative links']} relative links "
        f"({stats['links with a fragment']} with a fragment), {stats['external links']} absolute links, "
        f"{stats['code blocks']} code blocks, {stats['callouts']} callouts.\n"
        f"Code block languages: {language_list or 'none'}."
    )
    return print_report(report, summary)


if __name__ == "__main__":
    sys.exit(main())
