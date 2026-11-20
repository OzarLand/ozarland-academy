#!/usr/bin/env python3
"""Checks on the built portal (run after tools/site/build.py).

`zensical build --strict` validates the links it resolves itself. This script
looks at what was actually written to the output directory, whatever produced
it (Markdown, templates of overrides/, the theme, tools/site/releases.py).
The output directory holds the site of each available release under <id>/,
and the root of the portal (landing page, not-found page, versions.json, one
page per planned release).

On every page of the portal:

    link-file          every internal href/src of every HTML page, and every
                       url() of every stylesheet, points to a file of the
                       portal; this covers the links from one release to
                       another, such as those of the release selector
    link-anchor        every internal link with a #fragment points to an
                       element id of the target page
    external-resource  no page or stylesheet loads a script, a stylesheet, a
                       font, an image or a frame from another origin (plain
                       <a href> links to other sites are allowed and listed)
    runtime-request    nothing makes the theme bundle call a third-party host
                       at runtime: a page with a Mermaid diagram loads the
                       vendored Mermaid library, and no element asks for the
                       GitHub repository statistics
    page-empty         no page has an empty content area (a page with a title
                       and nothing else is a warning until --strict)
    canonical          the canonical address of a page is the page itself
    duplicate-id       an id used twice in a page (warning)

On the site of each available release:

    page-missing       every Markdown page of docs/<id>/ has its built page
    search-index       the search index of the release exists, is valid JSON,
                       has at least one entry per page, and every entry points
                       to an existing page and anchor of the same release
    sitemap            every URL of <id>/sitemap.xml is a page of the release
    updates            every page of <id>/assets/data/updates.json is built

On the root of the portal:

    portal-root        the learning path lists the modules of academy.toml
                       in order and opens the first available one; every
                       module has its home page; the home of the versioned
                       module links to its default release, which is built,
                       and its versions.json says what academy.toml says;
                       the not-found page knows the same sites; a planned
                       module or release has its "coming soon" page and
                       nothing else; no directory belongs to no site

It prints the number of pages, links, anchors and the external hosts linked.
Exit status: 0 when there is no error, 1 otherwise. With --strict every
warning is an error. Standard library only (Python 3.11 or newer).

Usage:  python3 tools/site/check_site.py site [--strict] [--release ID]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

# The page listing and the report format are shared with check_docs.py, which
# lives next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402
from check_docs import ROOT, Report, list_pages, print_report, release_config  # noqa: E402

RULES = (
    "link-file",
    "link-anchor",
    "external-resource",
    "runtime-request",
    "page-empty",
    "canonical",
    "duplicate-id",
    "page-missing",
    "search-index",
    "sitemap",
    "updates",
    "portal-root",
)

#: Used when the site URL is unknown, so that a link climbing above the site
#: root is still detected.
PLACEHOLDER_SITE_URL = "https://site.invalid/__root__/"

#: URL schemes that are not fetched as a resource or followed as a page.
INERT_SCHEMES = {"mailto", "tel", "javascript", "data", "blob", "about", "sms"}

#: `<link rel>` values that name another document instead of loading a file.
LINK_RELS_NOT_LOADED = {
    "canonical", "alternate", "prev", "next", "up", "first", "last", "index",
    "author", "help", "license", "me", "search", "bookmark", "nofollow",
}  # fmt: skip

#: (tag, attribute) pairs whose URL the browser fetches when the page loads.
RESOURCE_ATTRIBUTES = {
    ("script", "src"), ("img", "src"), ("img", "srcset"), ("source", "src"),
    ("source", "srcset"), ("video", "src"), ("video", "poster"), ("audio", "src"),
    ("track", "src"), ("iframe", "src"), ("frame", "src"), ("embed", "src"),
    ("object", "data"), ("input", "src"), ("use", "href"), ("use", "xlink:href"),
    ("image", "href"), ("image", "xlink:href"),
}  # fmt: skip

#: Elements whose text is not page content.
SILENT_ELEMENTS = {"script", "style", "template", "noscript", "svg", "nav"}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
}  # fmt: skip

SEARCH_INDEX_NAMES = ("search.json", "search/search_index.json")

_CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]*))\s*\)""", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"""@import\s+(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_JS_HOST = re.compile(r"""https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})""")
#: The Mermaid library itself (mermaid.min.js, mermaid.esm.min.mjs ...), not a
#: helper whose name merely contains the word (portal-mermaid.js).
_MERMAID_LIBRARY = re.compile(r"(?:^|/)mermaid(?:\.[\w.-]+)?\.m?js$", re.IGNORECASE)


@dataclass
class Reference:
    line: int
    url: str
    loaded: bool  # True: fetched when the page loads; False: a link to follow
    what: str  # e.g. `<script src>`


@dataclass
class Page:
    rel: str
    ids: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    base: str | None = None
    canonical: str | None = None
    has_article: bool = False
    has_main: bool = False
    text: dict[str, int] = field(default_factory=lambda: {"body": 0, "main": 0, "article": 0})
    body_text: dict[str, int] = field(default_factory=lambda: {"body": 0, "main": 0, "article": 0})
    theme_config: str = ""  # JSON of <script id="__config">, read by the theme bundle
    theme_config_line: int = 0
    mermaid_lines: list[int] = field(default_factory=list)
    source_component_lines: list[int] = field(default_factory=list)
    redirect: bool = False

    def content_text(self) -> tuple[str, int, int]:
        """(container, characters of text, characters outside the <h1>)."""
        container = "article" if self.has_article else "main" if self.has_main else "body"
        return container, self.text[container], self.body_text[container]


class PageParser(HTMLParser):
    """Collect ids, URLs and the amount of visible text of one HTML page."""

    def __init__(self, page: Page) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page
        self.stack: list[tuple[str, bool]] = []  # (tag, silent)
        self.silent = 0
        self.depth = {"main": 0, "article": 0, "h1": 0}
        self.style_line: int | None = None
        self.in_theme_config = False

    # -- elements ---------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: (value or "") for name, value in attrs}
        line = self.getpos()[0]
        page = self.page

        if values.get("id"):
            page.ids.append(values["id"])
        if tag == "a" and values.get("name") and values.get("name") != values.get("id"):
            page.ids.append(values["name"])
        classes = values.get("class", "").split()
        if "mermaid" in classes:
            page.mermaid_lines.append(line)
        if values.get("data-md-component") == "source":
            page.source_component_lines.append(line)

        if tag == "base" and "href" in values:
            page.base = values["href"]
        elif tag in ("a", "area") and "href" in values:
            page.references.append(Reference(line, values["href"], False, f"<{tag} href>"))
        elif tag == "link" and "href" in values:
            rels = set(values.get("rel", "").lower().split())
            loaded = not rels or not rels <= LINK_RELS_NOT_LOADED
            if "canonical" in rels:
                page.canonical = values["href"]
            page.references.append(
                Reference(line, values["href"], loaded, f"<link rel=\"{values.get('rel', '')}\" href>")
            )
        elif tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"url\s*=\s*['\"]?([^'\"]+)", values.get("content", ""), re.IGNORECASE)
            if match:
                page.redirect = True
                page.references.append(Reference(line, match.group(1).strip(), False, "<meta refresh>"))
        for (element, attribute) in RESOURCE_ATTRIBUTES:
            if tag == element and values.get(attribute):
                value = values[attribute]
                urls = (
                    [part.strip().split()[0] for part in value.split(",") if part.strip()]
                    if attribute == "srcset"
                    else [value]
                )
                for url in urls:
                    page.references.append(Reference(line, url, True, f"<{tag} {attribute}>"))
        if values.get("style"):
            for url in css_urls(values["style"]):
                page.references.append(Reference(line, url, True, f'<{tag} style="url()">'))

        if tag in VOID_ELEMENTS:
            return
        silent = tag in SILENT_ELEMENTS or "hidden" in values
        self.stack.append((tag, silent))
        self.silent += silent
        if tag in self.depth:
            self.depth[tag] += 1
        if tag == "article":
            page.has_article = True
        elif tag == "main":
            page.has_main = True
        elif tag == "style":
            self.style_line = line
        elif tag == "script" and values.get("id") == "__config":
            self.in_theme_config = True
            page.theme_config_line = line

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        # Close up to the matching open element (tolerates unclosed <p>, <li> ...).
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                for name, silent in self.stack[index:]:
                    self.silent -= silent
                    if name in self.depth:
                        self.depth[name] -= 1
                del self.stack[index:]
                break
        if tag == "style":
            self.style_line = None
        elif tag == "script":
            self.in_theme_config = False

    def handle_data(self, data: str) -> None:
        if self.in_theme_config:
            self.page.theme_config += data
        if self.style_line is not None:
            for url in css_urls(data):
                self.page.references.append(Reference(self.style_line, url, True, "<style> url()"))
        if self.silent:
            return
        size = len("".join(data.split()))
        if not size:
            return
        for container in ("body", "main", "article"):
            if container == "body" or self.depth[container] > 0:
                self.page.text[container] += size
                if self.depth["h1"] == 0:
                    self.page.body_text[container] += size


def css_urls(css: str) -> list[str]:
    """URLs a stylesheet makes the browser fetch: url(...) and @import."""
    css = _CSS_COMMENT.sub("", css)
    urls = []
    for match in _CSS_URL.finditer(css):
        urls.append(next(group for group in match.groups() if group is not None))
    for match in _CSS_IMPORT.finditer(css):
        urls.append(match.group(1) if match.group(1) is not None else match.group(2))
    return [url.strip() for url in urls if url.strip()]


class Site:
    def __init__(self, site_dir: Path, site_url: str, report: Report) -> None:
        self.dir = site_dir
        self.report = report
        self.files: set[str] = set()
        self.dirs: set[str] = set()
        for directory, dirnames, filenames in os.walk(site_dir):
            base = Path(directory).relative_to(site_dir).as_posix()
            base = "" if base == "." else base + "/"
            self.dirs.update(base + d for d in dirnames)
            self.files.update(base + f for f in filenames)

        self.pages: dict[str, Page] = {}
        for rel in sorted(f for f in self.files if f.endswith((".html", ".htm"))):
            page = Page(rel)
            parser = PageParser(page)
            parser.feed((site_dir / rel).read_text(encoding="utf-8", errors="replace"))
            parser.close()
            self.pages[rel] = page
        self.ids = {rel: set(page.ids) for rel, page in self.pages.items()}

        self.site_url_known = bool(site_url)
        if not site_url:
            index = self.pages.get("index.html")
            if index is not None and index.canonical and urlsplit(index.canonical).scheme:
                site_url = index.canonical
                self.site_url_known = True
        site_url = site_url or PLACEHOLDER_SITE_URL
        self.site_url = site_url if site_url.endswith("/") else site_url + "/"
        parts = urlsplit(self.site_url)
        self.host = parts.netloc.lower()
        self.base_path = parts.path

        #: Top-level directories that may be missing without an error: the
        #: sites of the releases a run with --release did not build.
        self.not_built: set[str] = set()
        self.stats = {"links": 0, "anchors": 0, "resources": 0, "external links": 0, "not built": 0}
        self.external_hosts: dict[str, int] = {}
        self.script_hosts: dict[str, int] = {}

    # -- URL resolution ---------------------------------------------------------

    def locate(self, source: str, url: str, base: str | None = None) -> tuple[str, str, str]:
        """Classify a URL found in the file `source` (site-relative path).

        Returns (kind, value, fragment):
          ("skip", "", "")                 nothing to check
          ("external", host, "")           another origin
          ("outside", absolute URL, "")    relative URL that leaves the site root
          ("missing", site path, "")       internal, but no such file
          ("file", site path, fragment)    internal file
        """
        url = url.strip()
        if not url:
            return "skip", "", ""
        parts = urlsplit(url)
        if parts.scheme.lower() in INERT_SCHEMES:
            return "skip", "", ""
        absolute_form = bool(parts.scheme) or url.startswith("//")
        if parts.scheme and parts.scheme.lower() not in ("http", "https"):
            return "external", f"{parts.scheme}:", ""

        here = urljoin(self.site_url, source)
        if base:
            here = urljoin(here, base)
        target = urlsplit(urljoin(here, url))
        inside = target.netloc.lower() == self.host and (
            target.path.startswith(self.base_path) or target.path + "/" == self.base_path
        )
        if not inside:
            if absolute_form:
                return "external", target.netloc.lower(), ""
            return "outside", target.geturl(), ""

        rel = unquote(target.path[len(self.base_path) :])
        fragment = unquote(target.fragment)
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        elif rel not in self.files and rel in self.dirs:
            rel += "/index.html"
        if rel not in self.files:
            if any(rel == path or rel.startswith(path + "/") for path in self.not_built):
                self.stats["not built"] += 1
                return "skip", "", ""
            return "missing", rel, ""
        return "file", rel, fragment

    # -- checks -------------------------------------------------------------------

    def check_references(self) -> None:
        error = self.report.error
        for rel, page in self.pages.items():
            for ref in page.references:
                kind, value, fragment = self.locate(rel, ref.url, page.base)
                if kind == "skip":
                    continue
                if kind == "external":
                    if ref.loaded:
                        error(
                            rel,
                            ref.line,
                            "external-resource",
                            f"{ref.what} loads `{ref.url}` from another origin ({value})",
                        )
                    else:
                        self.stats["external links"] += 1
                        self.external_hosts[value] = self.external_hosts.get(value, 0) + 1
                    continue
                self.stats["resources" if ref.loaded else "links"] += 1
                if kind == "outside":
                    error(rel, ref.line, "link-file", f"{ref.what} `{ref.url}` leaves the site ({value})")
                elif kind == "missing":
                    error(rel, ref.line, "link-file", f"{ref.what} `{ref.url}`: `{value}` is not in the site")
                elif "#" in ref.url and value in self.ids:
                    self.stats["anchors"] += 1
                    # An empty fragment and `#top` always scroll to the top of the page.
                    if fragment and fragment.lower() != "top" and fragment not in self.ids[value]:
                        error(
                            rel,
                            ref.line,
                            "link-anchor",
                            f"{ref.what} `{ref.url}`: no element with id `{fragment}` in `{value}`",
                        )

    def check_stylesheets(self) -> None:
        for rel in sorted(f for f in self.files if f.endswith(".css")):
            css = (self.dir / rel).read_text(encoding="utf-8", errors="replace")
            for url in css_urls(css):
                if url.startswith("#"):
                    continue
                kind, value, _ = self.locate(rel, url)
                if kind == "external":
                    self.report.error(
                        rel, 1, "external-resource", f"stylesheet loads `{url[:120]}` from another origin ({value})"
                    )
                elif kind in ("missing", "outside"):
                    self.report.error(rel, 1, "link-file", f"stylesheet url `{url[:120]}` is not in the site")
                elif kind == "file":
                    self.stats["resources"] += 1

    def scan_scripts(self) -> None:
        """Hosts named in JavaScript files: reported, never an error.

        A bundle names many URLs it never requests (licences, XML namespaces),
        so this list is only a pointer for a manual review.
        """
        for rel in sorted(f for f in self.files if f.endswith((".js", ".mjs"))):
            text = (self.dir / rel).read_text(encoding="utf-8", errors="replace")
            for host in _JS_HOST.findall(text):
                host = host.lower()
                if host != self.host:
                    self.script_hosts[host] = self.script_hosts.get(host, 0) + 1

    def check_runtime_requests(self) -> None:
        """Markup that makes the theme bundle request a third-party host.

        * A `.mermaid` element makes the bundle download Mermaid from
          unpkg.com unless `window.mermaid` already exists: such a page must
          load the vendored Mermaid library (a local `mermaid*.js`). A helper
          script that only defines a stand-in does not count: the diagrams
          would not render.
        * An element with `data-md-component="source"` makes the bundle ask
          api.github.com for the repository statistics.
        """
        for rel, page in self.pages.items():
            scripts = [
                self.locate(rel, ref.url, page.base)
                for ref in page.references
                if ref.what == "<script src>"
            ]
            local_mermaid = any(
                kind == "file" and _MERMAID_LIBRARY.search(value) for kind, value, _ in scripts
            )
            if page.mermaid_lines and not local_mermaid:
                self.report.error(
                    rel,
                    page.mermaid_lines[0],
                    "runtime-request",
                    f"{len(page.mermaid_lines)} Mermaid diagram(s) but the page does not load the vendored "
                    "Mermaid library: the diagrams do not render, or the theme bundle downloads Mermaid "
                    "from unpkg.com",
                )
            elif local_mermaid and not page.mermaid_lines:
                self.report.warning(
                    rel, 1, "runtime-request", "the Mermaid library is loaded on a page without a diagram"
                )
            for line in page.source_component_lines:
                self.report.error(
                    rel,
                    line,
                    "runtime-request",
                    'element with data-md-component="source": the theme bundle would request api.github.com',
                )

    def check_content(self) -> None:
        for rel, page in self.pages.items():
            if page.redirect:
                continue
            container, text, body_text = page.content_text()
            if text == 0:
                self.report.error(rel, 1, "page-empty", f"<{container}> has no text")
            elif body_text == 0 and not rel.endswith("404.html"):
                self.report.warning(rel, 1, "page-empty", f"<{container}> has a title and no other text")
            seen: set[str] = set()
            for value in page.ids:
                if value in seen:
                    self.report.warning(rel, 1, "duplicate-id", f"id `{value}` is used more than once")
                seen.add(value)
            if page.canonical and self.site_url_known and not rel.endswith("404.html"):
                kind, value, _ = self.locate(rel, page.canonical, page.base)
                if (kind, value) != ("file", rel):
                    self.report.error(
                        rel, 1, "canonical", f"canonical address `{page.canonical}` is not the address of this page"
                    )

    def page_file(self, source: str, directory_urls: bool, prefix: str = "") -> str | None:
        """Built file of a docs-relative Markdown path (None: not built).

        `prefix` is the directory of the release in the portal (`ussuri/`).
        """
        stem = prefix + source[: -len(".md")]
        folder, _, name = stem.rpartition("/")
        prefix = folder + "/" if folder else ""
        if name in ("index", "README"):
            candidates = [prefix + "index.html"]
        else:
            first = f"{stem}/index.html" if directory_urls else f"{stem}.html"
            second = f"{stem}.html" if directory_urls else f"{stem}/index.html"
            candidates = [first, second]
        return next((c for c in candidates if c in self.files), None)

    def check_sources(
        self, sources: list[str], docs_dir: str, directory_urls: bool, prefix: str = ""
    ) -> list[str]:
        """Every Markdown page has a built page. Returns the built files."""
        built = []
        for source in sources:
            target = self.page_file(source, directory_urls, prefix)
            if target is None:
                self.report.error(
                    f"{docs_dir}/{source}", 1, "page-missing", "Markdown page has no built page in the site"
                )
            else:
                built.append(target)
        return built

    def check_search_index(self, expected: list[str], prefix: str = "") -> int:
        """Search index of one site: present, valid, one entry per page, no dead entry."""
        error = self.report.error
        short = next((n for n in SEARCH_INDEX_NAMES if prefix + n in self.files), None)
        if short is None:
            error(prefix + SEARCH_INDEX_NAMES[0], 1, "search-index", "the search index file is missing")
            return 0
        name = prefix + short
        try:
            data = json.loads((self.dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            error(name, 1, "search-index", f"not valid JSON: {exc}")
            return 0
        items = data.get("items", data.get("docs")) if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            error(name, 1, "search-index", "no list of entries (`items`) in the search index")
            return 0

        indexed: dict[str, int] = {}
        for number, item in enumerate(items):
            location = item.get("location") if isinstance(item, dict) else None
            if not isinstance(location, str):
                error(name, 1, "search-index", f"entry {number} has no `location`")
                continue
            kind, value, fragment = self.locate(prefix + "index.html", location or "./")
            if kind != "file" or not value.startswith(prefix):
                error(name, 1, "search-index", f"entry {number} points to `{location}`, which is not in the site")
                continue
            indexed[value] = indexed.get(value, 0) + 1
            if fragment and value in self.ids and fragment not in self.ids[value]:
                error(
                    name,
                    1,
                    "search-index",
                    f"entry {number} points to `{location}`: no element with id `{fragment}` in `{value}`",
                )
        for page in expected:
            if page not in indexed:
                error(page, 1, "search-index", f"page has no entry in {name}")

        # The theme bundle loads `<base>/search.json` and starts the worker
        # named by `search`; both come from the configuration of each page.
        for rel, page in self.pages.items():
            if not rel.startswith(prefix) or not page.theme_config.strip():
                continue
            try:
                settings = json.loads(page.theme_config)
            except ValueError:
                error(rel, page.theme_config_line, "search-index", "theme configuration (#__config) is not valid JSON")
                continue
            if not isinstance(settings, dict):
                continue
            base, worker = settings.get("base"), settings.get("search")
            if isinstance(base, str) and short == "search.json":
                kind, value, _ = self.locate(rel, base.rstrip("/") + "/search.json", page.base)
                if (kind, value) != ("file", name):
                    error(
                        rel,
                        page.theme_config_line,
                        "search-index",
                        f"theme configuration: base `{base}` does not lead to {name}",
                    )
            if isinstance(worker, str) and self.locate(rel, worker, page.base)[0] != "file":
                error(
                    rel,
                    page.theme_config_line,
                    "search-index",
                    f"theme configuration: search worker `{worker}` is not in the site",
                )
        return len(items)

    def check_sitemap(self, prefix: str = "") -> int:
        """Every URL of a sitemap is a file of the portal, under `prefix`."""
        name = prefix + "sitemap.xml"
        if name not in self.files or not self.site_url_known:
            return 0
        try:
            root = ElementTree.parse(self.dir / name).getroot()
        except ElementTree.ParseError as exc:
            self.report.error(name, 1, "sitemap", f"not valid XML: {exc}")
            return 0
        count = 0
        for element in root.iter():
            if element.tag.rpartition("}")[2] != "loc" or not element.text:
                continue
            count += 1
            kind, value, _ = self.locate("index.html", element.text.strip())
            if kind != "file" or not value.startswith(prefix):
                self.report.error(name, 1, "sitemap", f"`{element.text.strip()}` is not a page of the site")
        return count

    def check_updates(self, prefix: str = "") -> None:
        """assets/data/updates.json (written by prebuild.py) only lists built pages."""
        name = prefix + "assets/data/updates.json"
        if name not in self.files:
            return
        try:
            data = json.loads((self.dir / name).read_text(encoding="utf-8"))
            pages = data["pages"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.report.error(name, 1, "updates", f"cannot be read: {exc!r}")
            return
        for entry in pages:
            url = entry.get("url") if isinstance(entry, dict) else None
            if not isinstance(url, str) or self.locate(prefix + "index.html", url or "./")[0] != "file":
                self.report.error(name, 1, "updates", f"entry `{url}` is not a page of the site")


    # -- root of the portal ---------------------------------------------------------

    def check_root(self, registry: releases.Registry, root: Path) -> None:
        """Learning path, homes and versions.json of the modules, not-found page, planned pages."""
        name = "portal-root"

        def error(path: str, message: str) -> None:
            self.report.error(path, 1, name, message)

        def text_of(path: str) -> str:
            return (self.dir / path).read_text(encoding="utf-8", errors="replace")

        # Learning path: every module, in order; the first available one is the start.
        if "index.html" not in self.files:
            error("index.html", "the page of the learning path is missing")
        else:
            text = text_of("index.html")
            listed = re.findall(r'data-portal-module="([^"]*)"', text)
            if listed != [m.id for m in registry.modules]:
                error("index.html", f"the learning path lists {listed}, {releases.REGISTRY_FILE} has {[m.id for m in registry.modules]}")
            start = re.search(r'data-portal-start="([^"]*)"', text)
            first = next((m for m in registry.modules if m.available), None)
            if first is not None and (not start or start.group(1) != first.id):
                error("index.html", f"the call to action does not open the first available module `{first.id}`")

        for module in registry.modules:
            home = f"{module.id}/index.html"
            if home not in self.files and module.id not in self.not_built:
                error(home, f"the home page of the module `{module.id}` is missing")
                continue
            if not module.versioned:
                continue
            # Home of a versioned module: links to its default release, which must be there.
            text = text_of(home)
            default = f"{module.id}/{module.default}"
            match = re.search(r'data-portal-default="([^"]*)"', text)
            if not match:
                error(home, "the home of the module does not name the default release (data-portal-default)")
            elif match.group(1) != default:
                error(home, f"the home of the module links to `{match.group(1)}`, the default release is `{default}`")
            if f"{default}/index.html" not in self.files and default not in self.not_built:
                error(home, f"the default release is not built: {default}/index.html is missing")
            # versions.json says what the registry says.
            versions = f"{module.id}/versions.json"
            expected = releases.versions_json(registry, module)
            if versions not in self.files:
                error(versions, "the file is missing")
            else:
                try:
                    data = json.loads(text_of(versions))
                except ValueError as exc:
                    error(versions, f"not valid JSON: {exc}")
                else:
                    if data != expected:
                        listed = [e.get("version") for e in data if isinstance(e, dict)] if isinstance(data, list) else []
                        error(
                            versions,
                            f"does not match {releases.REGISTRY_FILE} (lists {listed}, the registry has "
                            f"{[r.id for r in module.releases]}): build the portal again",
                        )

        # Not-found page: the sites it knows are those of the registry.
        if "404.html" not in self.files:
            error("404.html", "the not-found page of the portal is missing")
        else:
            match = re.search(
                r'<script id="portal-not-found" type="application/json">(.*?)</script>', text_of("404.html"), re.DOTALL
            )
            data = None
            if match:
                try:
                    data = json.loads(match.group(1))
                except ValueError:
                    data = None
            if not isinstance(data, dict):
                error("404.html", "the data of the redirections (script #portal-not-found) is missing or not valid JSON")
            else:
                known = [(r.get("path"), r.get("status")) for r in data.get("sites", []) if isinstance(r, dict)]
                if known != [(r.path, r.status) for r in registry.releases]:
                    error("404.html", f"the sites it knows do not match {releases.REGISTRY_FILE}")

        # Planned modules and releases: the "coming soon" page and nothing else.
        for release in registry.planned:
            page = f"{release.path}/index.html"
            if page not in self.files:
                error(page, f"the page of the planned `{release.path}` is missing")
                continue
            others = sorted(f for f in self.files if f.startswith(release.path + "/") and f != page)
            if others:
                error(page, f"a planned module or release has one page only, found also: {', '.join(others[:5])}")
            text = html_unescape(text_of(page))
            if release.title not in text or not ("not available yet" in text or "coming soon" in text):
                error(page, "the page does not name the module or release, or does not say that it is not available yet")

        # Available sites, and nothing that belongs to no site.
        for release in registry.available:
            if f"{release.path}/index.html" not in self.files and release.path not in self.not_built:
                error(f"{release.path}/index.html", f"`{release.path}` is available but its site is not built")
        modules = {m.id: m for m in registry.modules}
        for directory in sorted(d for d in self.dirs if "/" not in d):
            if directory != "assets" and directory not in modules:
                error(directory + "/", f"directory of no module of {releases.REGISTRY_FILE}")
        for module in registry.modules:
            if module.versioned:
                for directory in sorted(d for d in self.dirs if d.count("/") == 1 and d.startswith(module.id + "/")):
                    if directory.split("/")[1] not in {r.id for r in module.releases}:
                        error(directory + "/", f"directory of no release of the module `{module.id}`")
        self.check_sitemap()


def html_unescape(text: str) -> str:
    return html.unescape(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Checks on the built portal.")
    parser.add_argument("site_dir", type=Path, help="output directory of the build (site)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    parser.add_argument(
        "--release",
        metavar="PATH",
        help="only this site was built (day2/2024.1, lab): check it and the root, accept that the others are missing",
    )
    parser.add_argument("--site-url", default=None, help="public URL of the portal root (default: https://<SITE_DOMAIN>/, or site_url of zensical.base.toml)")
    parser.add_argument("--strict", action="store_true", help="report warnings as errors")
    args = parser.parse_args(argv)

    site_dir = args.site_dir.resolve()
    if not site_dir.is_dir():
        print(f"check_site: {site_dir} is not a directory (run the build first)", file=sys.stderr)
        return 1
    root = args.root.resolve()
    try:
        registry = releases.load_registry(root)
        selected = releases.select(registry, args.release)
        base = releases.load_project(root / releases.BASE_CONFIG)
        root_url = args.site_url or releases.portal_root_url(base)
    except releases.RegistryError as exc:
        for problem in exc.problems:
            print(f"check_site: {problem}", file=sys.stderr)
        return 1

    report = Report(strict=args.strict)
    site = Site(site_dir, root_url, report)
    if not site.pages:
        print(f"check_site: no HTML page in {site_dir}", file=sys.stderr)
        return 1
    if args.release:
        site.not_built = {
            release.path
            for release in registry.available
            if release not in selected and f"{release.path}/index.html" not in site.files
        }

    site.check_references()
    site.check_stylesheets()
    site.scan_scripts()
    site.check_runtime_requests()
    site.check_content()

    lines = []
    for release in selected:
        prefix = release.path + "/"
        config = release_config(root, registry, release)
        if config.error:
            report.error(release.settings_file, 1, "portal-root", f"configuration cannot be read: {config.error}")
            continue
        if not (root / release.docs_dir).is_dir():
            report.error(release.docs_dir, 1, "page-missing", "the docs directory of the site does not exist")
            continue
        sources = list_pages(root, config, release.docs_dir)
        expected = site.check_sources(sources, release.docs_dir, config.use_directory_urls, prefix)
        entries = site.check_search_index(expected, prefix)
        sitemap = site.check_sitemap(prefix)
        site.check_updates(prefix)
        lines.append(
            f"Site {release.path}: {len(expected)} of {len(sources)} Markdown page(s) of {release.docs_dir}/ are built; "
            f"search index: {entries} entries; sitemap: {sitemap} URL(s) checked."
        )
    site.check_root(registry, root)

    stats = site.stats
    ids = sum(len(values) for values in site.ids.values())
    hosts = ", ".join(f"{host} ({count})" for host, count in sorted(site.external_hosts.items())) or "none"
    script_hosts = ", ".join(sorted(site.script_hosts)) or "none"
    planned = ", ".join(release.path for release in registry.planned) or "none"
    skipped = (
        f"\nNot built in this run, links to them not checked ({stats['not built']}): {', '.join(sorted(site.not_built))}."
        if site.not_built
        else ""
    )
    summary = (
        f"Portal: {site_dir}\n"
        f"Portal URL: {site.site_url}\n"
        + "\n".join(lines)
        + f"\nRoot: learning path ({len(registry.modules)} modules), not-found page, versions.json; "
        f"planned modules and releases with their page: {planned}.{skipped}\n"
        f"Pages: {len(site.pages)} HTML page(s) in the portal.\n"
        f"Links: {stats['links']} internal link(s), {stats['anchors']} with an anchor, checked against {ids} element id(s); "
        f"{stats['resources']} internal resource reference(s) (scripts, stylesheets, images, fonts).\n"
        f"External links (plain <a href>): {stats['external links']} to {len(site.external_hosts)} host(s): {hosts}.\n"
        f"Hosts named in JavaScript files (not a check; a bundle names URLs it never requests): {script_hosts}."
    )
    return print_report(report, summary, tool="check_site", annotate_files=False)


if __name__ == "__main__":
    sys.exit(main())
