#!/usr/bin/env python3
"""Modules and releases of the portal: the registry and what is generated from it.

OzarLand Academy is one learning path made of modules (academy.toml). A
module is either one site ("single") or one site per release ("versioned",
the day-2 module). Every site is self-contained and published under its own
URL prefix, its *path*: `<module>` or `<module>/<release>`. A small root site
holds what is shared:

    site/index.html             the learning path: the modules in order
    site/404.html               not-found page of the whole portal
    site/sitemap.xml            index of the sitemaps of the sites
    site/CNAME                  the custom domain, when SITE_DOMAIN is set
    site/assets/                theme files used by the root pages
    site/<path>/                site of an available module or release (built
                                by Zensical from docs/<path>/)
    site/<module>/index.html    home of a versioned module (its releases), or
                                the only page of a planned module
    site/<module>/versions.json the releases of a versioned module
    site/<module>/<id>/index.html   only page of a planned release

Sources:

    academy.toml                the registry: modules, releases, defaults
    zensical.base.toml          site configuration shared by all sites
    docs/<path>.toml            settings of one site (nav, description)
    docs/<path>/                its Markdown
    overrides/                  templates and static files shared by all sites

The address of the portal root is https://<SITE_DOMAIN>/ when the
environment variable SITE_DOMAIN is set, and `site_url` of
zensical.base.toml otherwise (portal_root_url): nothing else may write it.

This module reads the registry and writes what Zensical needs. Zensical only
accepts a docs directory inside the directory of its configuration file, and
its TOML format has no include, so the configurations that are built are
generated at the repository root and are git-ignored:

    .zensical.<name>.toml       zensical.base.toml merged with docs/<path>.toml
                                (<name> is the path with "/" replaced by "_")
    .zensical._root.toml        configuration of the root site
    .build/root/docs/           Markdown stubs of the root site; the text of
                                these pages is in the templates of overrides/
    .build/root/site/           the root site as built, before `assemble`
                                copies it into site/

Command line (tools/site/build.py calls the same functions):

    python3 tools/site/releases.py list [--status available|planned|all]
    python3 tools/site/releases.py default
    python3 tools/site/releases.py url             print the portal address
    python3 tools/site/releases.py config <path>   write the configuration of a site
    python3 tools/site/releases.py root            write the root docs and config
    python3 tools/site/releases.py assemble        copy the root site into site/

A site is named by its path ("day2/2024.1", "lab") or, when no other site
has it, by its last segment ("2024.1").

Standard library only (Python 3.11 or newer, for tomllib).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

if sys.version_info < (3, 11):  # pragma: no cover - depends on the interpreter
    sys.exit("releases: Python 3.11 or newer is required (tomllib)")

import tomllib

ROOT = Path(__file__).resolve().parents[2]

REGISTRY_FILE = "academy.toml"
BASE_CONFIG = "zensical.base.toml"
#: Parent of the docs of every site. A site is DOCS_ROOT/<path>/ and its
#: settings are DOCS_ROOT/<path>.toml.
DOCS_ROOT = "docs"
#: Output directory. A site is SITE_DIR/<path>/.
SITE_DIR = "site"
#: Generated files of the root site (git-ignored).
ROOT_BUILD = ".build/root"
#: Name used for the root site where the name of a site is expected.
ROOT_NAME = "_root"
#: Environment variable that holds the custom domain of the portal.
DOMAIN_VARIABLE = "SITE_DOMAIN"

AVAILABLE = "available"
PLANNED = "planned"
STATUSES = (AVAILABLE, PLANNED)
SINGLE = "single"
VERSIONED = "versioned"
KINDS = (SINGLE, VERSIONED)

#: A module id is a directory name and a URL segment.
MODULE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: A release id is a directory name and a URL segment.
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
#: Names the root of the built portal uses for something else.
RESERVED_IDS = frozenset({"assets", "search", "index", "404", "versions", "sitemap", "cname"})
#: A domain name, without scheme, port or path.
DOMAIN_PATTERN = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")

#: Keys of docs/<path>.toml that the tooling sets itself.
DERIVED_KEYS = ("docs_dir", "site_dir", "site_url")

#: Theme features that need the navigation or the search of a site; the root
#: site has neither.
ROOT_DROPPED_FEATURES = ("navigation.", "toc.", "search.", "content.action.")

INDEX_NAMES = ("index.md", "README.md")
#: Not pages: generated data of a site (updates.json).
SKIPPED_TOP_DIRS = ("assets",)


class RegistryError(Exception):
    """academy.toml, or a file it refers to, cannot be used."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Release:
    """A site of the portal, or the place of a planned one.

    A release of a versioned module (`versioned` true), or a single module
    (`versioned` false: `id` and `module` are the module id and there is no
    OpenStack release).
    """

    id: str
    status: str
    openstack: str
    kolla_ansible: str
    title: str
    tag: str = ""
    module: str = ""
    versioned: bool = True

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE

    @property
    def path(self) -> str:
        """URL prefix of the site, its directory under docs/ and under site/."""
        return f"{self.module}/{self.id}" if self.versioned else self.module

    @property
    def docs_dir(self) -> str:
        return f"{DOCS_ROOT}/{self.path}"

    @property
    def settings_file(self) -> str:
        return f"{DOCS_ROOT}/{self.path}.toml"

    @property
    def config_name(self) -> str:
        """Name of the generated configuration (.zensical.<name>.toml)."""
        return self.path.replace("/", "_")

    @property
    def up(self) -> str:
        """Relative path from the base of the site to the portal root."""
        return "../" * (self.path.count("/") + 1)

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "module": self.module,
            "path": self.path,
            "status": self.status,
            "title": self.title,
            "openstack": self.openstack,
            "kolla_ansible": self.kolla_ansible,
            "tag": self.tag,
        }


@dataclass(frozen=True)
class Module:
    id: str
    step: str
    title: str
    summary: str
    kind: str
    status: str
    default: str = ""
    releases: tuple[Release, ...] = ()

    @property
    def versioned(self) -> bool:
        return self.kind == VERSIONED

    @property
    def available(self) -> bool:
        """A versioned module always has a home page; a single one when available."""
        return self.versioned or self.status == AVAILABLE

    @property
    def docs_dir(self) -> str:
        return f"{DOCS_ROOT}/{self.id}"

    @property
    def settings_file(self) -> str:
        return f"{DOCS_ROOT}/{self.id}.toml"

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": self.id,
            "step": self.step,
            "title": self.title,
            "summary": self.summary,
            "kind": self.kind,
            "status": AVAILABLE if self.available else PLANNED,
            "default": self.default,
        }


@dataclass(frozen=True)
class Registry:
    modules: tuple[Module, ...]

    @property
    def releases(self) -> tuple[Release, ...]:
        """Every site of the portal, available or planned, in the order of the path.

        A single module is one entry; a versioned module, one per release.
        """
        sites: list[Release] = []
        for module in self.modules:
            if module.versioned:
                sites.extend(module.releases)
            else:
                sites.append(
                    Release(
                        id=module.id,
                        status=module.status,
                        openstack="",
                        kolla_ansible="",
                        title=module.title,
                        module=module.id,
                        versioned=False,
                    )
                )
        return tuple(sites)

    def module(self, module_id: str) -> Module | None:
        return next((m for m in self.modules if m.id == module_id), None)

    def module_of(self, release: Release) -> Module:
        module = self.module(release.module)
        assert module is not None
        return module

    def get(self, name: str) -> Release | None:
        """The site named by its path, or by its last segment when that is unique."""
        exact = next((r for r in self.releases if r.path == name), None)
        if exact is not None:
            return exact
        matches = [r for r in self.releases if r.id == name]
        return matches[0] if len(matches) == 1 else None

    @property
    def versioned_module(self) -> Module | None:
        return next((m for m in self.modules if m.versioned), None)

    @property
    def default(self) -> str:
        """Path of the default release of the versioned module ("" without one)."""
        module = self.versioned_module
        return f"{module.id}/{module.default}" if module else ""

    @property
    def available(self) -> tuple[Release, ...]:
        return tuple(r for r in self.releases if r.available)

    @property
    def planned(self) -> tuple[Release, ...]:
        return tuple(r for r in self.releases if not r.available)

    @property
    def ids(self) -> tuple[str, ...]:
        """Paths of every site, available or planned."""
        return tuple(r.path for r in self.releases)


# --- registry ---------------------------------------------------------------


def _text(block: dict, key: str, where: str, problems: list[str]) -> str:
    value = block.get(key, "")
    if not isinstance(value, str):
        problems.append(f"{where}: `{key}` is not a text")
        return ""
    return value.strip()


def _parse_releases(module_id: str, blocks: object, problems: list[str]) -> list[Release]:
    if not isinstance(blocks, list) or not blocks:
        problems.append(f"module `{module_id}`: a versioned module needs [[module.release]] blocks")
        return []
    known = {"id", "status", "openstack", "kolla_ansible", "tag", "title"}
    releases: list[Release] = []
    seen: set[str] = set()
    for number, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            problems.append(f"module `{module_id}`: [[module.release]] block {number} is not a table")
            continue
        release_id = block.get("id")
        where = (
            f"release `{module_id}/{release_id}`"
            if isinstance(release_id, str)
            else f"module `{module_id}`: [[module.release]] block {number}"
        )
        if not isinstance(release_id, str) or not ID_PATTERN.match(release_id):
            problems.append(f"{where}: `id` must be made of lowercase letters, digits, dots and hyphens")
            continue
        if release_id in RESERVED_IDS or release_id.startswith("_"):
            problems.append(f"{where}: this id is reserved")
        if release_id in seen:
            problems.append(f"{where}: the id is used twice")
        seen.add(release_id)
        for key in sorted(set(block) - known):
            problems.append(f"{where}: unknown key `{key}`")
        values = {key: _text(block, key, where, problems) for key in ("status", "openstack", "kolla_ansible", "tag", "title")}
        if values["status"] not in STATUSES:
            problems.append(f"{where}: `status` must be one of: {', '.join(STATUSES)}")
        for key in ("openstack", "kolla_ansible"):
            if not values[key]:
                problems.append(f"{where}: `{key}` is missing")
        if values["status"] == AVAILABLE and not values["tag"]:
            problems.append(f"{where}: an available release needs `tag`, the upstream tag that is studied")
        title = values["title"] or f"{values['openstack']} · Kolla-Ansible {values['kolla_ansible']}"
        releases.append(
            Release(
                id=release_id,
                status=values["status"],
                openstack=values["openstack"],
                kolla_ansible=values["kolla_ansible"],
                title=title,
                tag=values["tag"],
                module=module_id,
            )
        )
    return releases


def parse_registry(data: object) -> Registry:
    """Build the registry from the content of academy.toml.

    Raises RegistryError with every problem found, not only the first one.
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        raise RegistryError(["the file is not a TOML table"])
    blocks = data.get("module")
    if not isinstance(blocks, list) or not blocks:
        raise RegistryError(["no [[module]] block"])
    for key in sorted(set(data) - {"module"}):
        problems.append(f"unknown key `{key}`")

    known = {"id", "step", "title", "summary", "kind", "status", "default", "release"}
    modules: list[Module] = []
    seen: set[str] = set()
    for number, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            problems.append(f"[[module]] block {number} is not a table")
            continue
        module_id = block.get("id")
        where = f"module `{module_id}`" if isinstance(module_id, str) else f"[[module]] block {number}"
        if not isinstance(module_id, str) or not MODULE_ID_PATTERN.match(module_id):
            problems.append(f"{where}: `id` must be made of lowercase letters, digits and hyphens")
            continue
        if module_id in RESERVED_IDS:
            problems.append(f"{where}: this id is reserved for the root of the portal")
        if module_id in seen:
            problems.append(f"{where}: the id is used twice")
        seen.add(module_id)
        for key in sorted(set(block) - known):
            problems.append(f"{where}: unknown key `{key}`")
        values = {key: _text(block, key, where, problems) for key in ("step", "title", "summary", "kind", "status", "default")}
        for key in ("step", "title", "summary"):
            if not values[key]:
                problems.append(f"{where}: `{key}` is missing")
        kind = values["kind"]
        releases: list[Release] = []
        if kind == SINGLE:
            if values["status"] not in STATUSES:
                problems.append(f"{where}: `status` must be one of: {', '.join(STATUSES)}")
            for key in ("default", "release"):
                if key in block:
                    problems.append(f"{where}: `{key}` belongs to a versioned module")
        elif kind == VERSIONED:
            if "status" in block:
                problems.append(f"{where}: a versioned module has no `status`; its releases have one")
            releases = _parse_releases(module_id, block.get("release"), problems)
            by_id = {r.id: r for r in releases}
            default = values["default"]
            if default not in by_id:
                problems.append(f"{where}: `default` must be the id of one of its releases")
            elif not by_id[default].available:
                problems.append(f"{where}: `default` is `{default}`, which is not available")
        else:
            problems.append(f"{where}: `kind` must be one of: {', '.join(KINDS)}")
        modules.append(
            Module(
                id=module_id,
                step=values["step"],
                title=values["title"],
                summary=values["summary"],
                kind=kind,
                status=values["status"] if kind == SINGLE else "",
                default=values["default"] if kind == VERSIONED else "",
                releases=tuple(releases),
            )
        )
    if sum(1 for m in modules if m.versioned) > 1:
        problems.append("only one module can be versioned (the release selector serves one module)")

    if problems:
        raise RegistryError(problems)
    return Registry(tuple(modules))


def load_registry(root: Path = ROOT) -> Registry:
    """Read academy.toml. Raises RegistryError."""
    path = root / REGISTRY_FILE
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise RegistryError([f"{REGISTRY_FILE} does not exist"]) from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryError([f"cannot be read: {exc}"]) from exc
    return parse_registry(data)


def _presence_problems(root: Path, release: Release) -> list[str]:
    problems = []
    name = f"release `{release.path}`" if release.versioned else f"module `{release.path}`"
    has_dir = (root / release.docs_dir).is_dir()
    has_settings = (root / release.settings_file).is_file()
    if release.available:
        if not has_dir:
            problems.append(f"{name} is available but {release.docs_dir}/ does not exist")
        if not has_settings:
            problems.append(f"{name} is available but {release.settings_file} does not exist")
    else:
        if has_dir:
            problems.append(
                f"{name} is planned but {release.docs_dir}/ exists: "
                f"set its status to `{AVAILABLE}`, or remove the directory"
            )
        if has_settings:
            problems.append(
                f"{name} is planned but {release.settings_file} exists: "
                f"set its status to `{AVAILABLE}`, or remove the file"
            )
    return problems


def layout_problems(root: Path, registry: Registry) -> list[str]:
    """Differences between the registry and the docs tree.

    An available site has its directory and its settings file; a planned
    one has neither; nothing else sits under docs/ or directly under the
    directory of a versioned module.
    """
    problems = []
    for release in registry.releases:
        problems += _presence_problems(root, release)

    def stray(directory: Path, names: set[str], where: str, what: str) -> None:
        for entry in sorted(directory.iterdir()):
            name = entry.name
            rel = f"{where}/{name}"
            if entry.is_dir():
                if name not in names:
                    problems.append(f"{rel}/ is not a {what} of {REGISTRY_FILE}")
            elif name.endswith(".toml"):
                if name[: -len(".toml")] not in names:
                    problems.append(f"{rel} does not belong to a {what} of {REGISTRY_FILE}")
            elif not name.startswith("."):
                problems.append(f"{rel}: files belong to the directory of a site, shared files to overrides/assets/")

    docs = root / DOCS_ROOT
    if docs.is_dir():
        stray(docs, {m.id for m in registry.modules}, DOCS_ROOT, "module")
        for module in registry.modules:
            if module.versioned and (root / module.docs_dir).is_dir():
                stray(root / module.docs_dir, {r.id for r in module.releases}, module.docs_dir, "release")
            if module.versioned and (root / module.settings_file).is_file():
                problems.append(f"{module.settings_file}: a versioned module has one settings file per release")
    return problems


# --- configuration ----------------------------------------------------------


def merge(base: dict, override: dict) -> dict:
    """`override` over `base`: tables are merged, everything else is replaced."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_project(path: Path) -> dict:
    """The `[project]` table of a TOML file. Raises RegistryError."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise RegistryError([f"{path.name} does not exist"]) from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryError([f"{path.name} cannot be read: {exc}"]) from exc
    project = data.get("project", {})
    if not isinstance(project, dict):
        raise RegistryError([f"{path.name}: `project` is not a table"])
    return project


def site_domain(environ: dict | None = None) -> str:
    """The custom domain of SITE_DOMAIN, "" when the variable is unset or empty.

    Raises RegistryError when it is not a plain domain name.
    """
    environ = os.environ if environ is None else environ
    domain = str(environ.get(DOMAIN_VARIABLE, "")).strip().lower().rstrip(".")
    if domain and not DOMAIN_PATTERN.match(domain):
        raise RegistryError(
            [f"{DOMAIN_VARIABLE} is `{domain}`: write a domain name only, such as academy.example.org "
             "(no scheme, port or path)"]
        )
    return domain


def portal_root_url(base: dict, environ: dict | None = None) -> str:
    """Address of the portal root, ending with "/".

    https://<SITE_DOMAIN>/ when SITE_DOMAIN is set, `site_url` of
    zensical.base.toml otherwise. Every tool asks this function: no other
    place writes the address of the portal.
    """
    domain = site_domain(environ)
    if domain:
        return f"https://{domain}/"
    url = base.get("site_url")
    if not isinstance(url, str) or not url:
        raise RegistryError([f"{BASE_CONFIG}: `site_url` (default address of the portal root) is missing"])
    return url if url.endswith("/") else url + "/"


def portal_data(registry: Registry, base: dict, current: Release | None, root_page: str = "") -> dict:
    """`extra.portal` of a built configuration: what the templates read.

    `up` is the path from the base of the built site to the portal root;
    `root_path` the path of the portal root on its host ("/ozarland-academy/"
    on github.io, "/" on a domain), for the not-found page, which is served
    at any depth.
    `releases` are the sites of the current module (the version selector);
    on the root site, those of the versioned module. `sites` are all the
    sites, available or planned (the not-found page reads them).
    """
    if current is not None:
        module = registry.module_of(current)
    else:
        module = registry.versioned_module
    module_releases = [r for r in registry.releases if module is not None and r.module == module.id]
    root_url = portal_root_url(base)
    return {
        "kind": "release" if current else "root",
        "current": current.id if current else "",
        "path": current.path if current else "",
        "module": module.as_dict() if module else {},
        "up": current.up if current else "",
        "default": registry.default,
        "root_url": root_url,
        "root_path": urlsplit(root_url).path or "/",
        "modules": [m.as_dict() for m in registry.modules],
        "releases": [release.as_dict() for release in module_releases],
        "sites": [release.as_dict() for release in registry.releases],
    }


def release_project(root: Path, registry: Registry, name: str, site_dir: str = SITE_DIR) -> dict:
    """Configuration of one available site (a release, or a single module)."""
    release = registry.get(name)
    if release is None:
        raise RegistryError([f"`{name}` is not a site of {REGISTRY_FILE}"])
    if not release.available:
        raise RegistryError([f"`{release.path}` is planned: it has no site to build"])
    base = load_project(root / BASE_CONFIG)
    own = load_project(root / release.settings_file)
    forbidden = [key for key in DERIVED_KEYS if key in own]
    if forbidden:
        raise RegistryError(
            [f"{release.settings_file}: `{key}` is set by the tooling and must not be set here" for key in forbidden]
        )
    project = merge(base, own)
    if "site_name" not in own:
        project["site_name"] = registry.module_of(release).title
    project["docs_dir"] = release.docs_dir
    project["site_dir"] = f"{site_dir}/{release.path}"
    project["site_url"] = f"{portal_root_url(base)}{release.path}/"
    if "edit_uri" not in own:
        prefix = base.get("edit_uri", "")
        prefix = prefix if not prefix or prefix.endswith("/") else prefix + "/"
        project["edit_uri"] = f"{prefix}{release.docs_dir}/"
    extra = project.setdefault("extra", {})
    extra["portal"] = portal_data(registry, base, release)
    return project


def page_url(rel: Path) -> str:
    """Directory URL of a page, relative to the site root (as Zensical builds it)."""
    if rel.name in INDEX_NAMES:
        parent = rel.parent.as_posix()
        return "" if parent == "." else f"{parent}/"
    return f"{rel.with_suffix('').as_posix()}/"


def page_urls(root: Path, release: Release) -> list[str]:
    """URLs of the pages of an available site, relative to its site root."""
    docs = root / release.docs_dir
    urls = []
    for path in sorted(docs.rglob("*.md")):
        rel = path.relative_to(docs)
        if rel.parts[0] not in SKIPPED_TOP_DIRS:
            urls.append(page_url(rel))
    return urls


def root_pages(registry: Registry) -> dict[str, dict]:
    """The pages of the root site: their stub path and front matter."""
    stubs: dict[str, dict] = {}
    for module in registry.modules:
        if module.versioned:
            stubs[f"{module.id}/index.md"] = {
                "template": "landing.html",
                "title": module.title,
                "description": module.summary,
                "portal_module": module.id,
            }
        elif not module.available:
            stubs[f"{module.id}/index.md"] = {
                "template": "planned.html",
                "title": module.title,
                "description": f"{module.title} is not available yet.",
                "portal_module": module.id,
            }
    for release in registry.planned:
        if release.versioned:
            stubs[f"{release.path}/index.md"] = {
                "template": "planned.html",
                "title": release.title,
                "description": f"The study of {release.title} is not available yet.",
                "portal_module": release.module,
                "portal_release": release.id,
            }
    return stubs


def root_project(root: Path, registry: Registry) -> dict:
    """Configuration of the root site: the learning path, module homes, not-found and planned pages."""
    base = load_project(root / BASE_CONFIG)
    project = copy.deepcopy(base)
    project["docs_dir"] = f"{ROOT_BUILD}/docs"
    project["site_dir"] = f"{ROOT_BUILD}/site"
    project["site_url"] = portal_root_url(base)
    project["nav"] = ["index.md", *root_pages(registry)]
    project.pop("edit_uri", None)
    theme = project.get("theme")
    if isinstance(theme, dict) and isinstance(theme.get("features"), list):
        theme["features"] = [
            feature for feature in theme["features"] if not str(feature).startswith(ROOT_DROPPED_FEATURES)
        ]
    extra = project.setdefault("extra", {})
    extra["portal"] = portal_data(registry, base, None)
    return project


# --- TOML output ------------------------------------------------------------


def _toml_string(value: str) -> str:
    # A JSON string is a TOML basic string, except for U+007F.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{ " + ", ".join(f"{_toml_string(str(k))} = {_toml_value(v)}" for k, v in value.items()) + " }"
    raise TypeError(f"cannot write {type(value).__name__} as TOML")


def dump_toml(project: dict, header: str = "") -> str:
    """TOML text of a `[project]` table (nested tables are written inline)."""
    lines = [f"# {line}".rstrip() for line in header.splitlines()]
    if lines:
        lines.append("")
    lines.append("[project]")
    for key, value in project.items():
        if isinstance(value, list) and value:
            lines.append(f"{_toml_string(key)} = [")
            lines.extend(f"  {_toml_value(item)}," for item in value)
            lines.append("]")
        else:
            lines.append(f"{_toml_string(key)} = {_toml_value(value)}")
    text = "\n".join(lines) + "\n"
    if tomllib.loads(text) != {"project": project}:  # pragma: no cover - guards the writer
        raise RuntimeError("generated TOML does not read back as the configuration")
    return text


def write_if_changed(path: Path, content: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def config_path(root: Path, name: str) -> Path:
    return root / f".zensical.{name}.toml"


def write_release_config(root: Path, registry: Registry, name: str, site_dir: str = SITE_DIR) -> Path:
    project = release_project(root, registry, name, site_dir)
    release = registry.get(name)
    path = config_path(root, release.config_name)
    header = (
        f"Generated by tools/site/releases.py from {BASE_CONFIG}, {release.settings_file}\n"
        f"and {REGISTRY_FILE}. Do not edit and do not commit."
    )
    write_if_changed(path, dump_toml(project, header))
    return path


def write_root(root: Path, registry: Registry) -> Path:
    """Write the Markdown stubs and the configuration of the root site."""
    project = root_project(root, registry)
    docs = root / ROOT_BUILD / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    stubs = {
        "index.md": {
            "template": "academy.html",
            "title": project.get("site_name", ""),
            "description": project.get("site_description", ""),
        },
        **root_pages(registry),
    }
    for rel, front in stubs.items():
        # A JSON string is a YAML double-quoted scalar.
        lines = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items()]
        text = "---\n" + "\n".join(lines) + f"\n---\n\n# {front['title']}\n"
        write_if_changed(docs / rel, text)
    path = config_path(root, ROOT_NAME)
    header = (
        f"Generated by tools/site/releases.py from {BASE_CONFIG} and {REGISTRY_FILE}:\n"
        "the root site of the portal. Do not edit and do not commit."
    )
    write_if_changed(path, dump_toml(project, header))
    return path


# --- root of the built portal -----------------------------------------------


def versions_json(registry: Registry, module: Module) -> list[dict]:
    """Content of site/<module>/versions.json, for a versioned module.

    The list has the form the tool `mike` writes (`version`, `title`,
    `aliases`), so that other tools can read it; what the portal adds is under
    `properties`.
    """
    return [
        {
            "version": release.id,
            "title": release.title,
            "aliases": [],
            "properties": {
                "status": release.status,
                "default": release.id == module.default,
                "openstack": release.openstack,
                "kolla_ansible": release.kolla_ansible,
                "tag": release.tag,
            },
        }
        for release in module.releases
    ]


def sitemap_index(registry: Registry, root_url: str, site: Path) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for release in registry.available:
        if (site / release.path / "sitemap.xml").is_file():
            lines.append(f"  <sitemap><loc>{root_url}{release.path}/sitemap.xml</loc></sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines) + "\n"


def _clean(site: Path, registry: Registry) -> None:
    """Remove what an earlier build left: anything that is not an available site."""
    keep = {release.path for release in registry.available}
    for entry in sorted(site.iterdir()):
        if entry.is_file():
            entry.unlink()
            continue
        if entry.name in keep:
            continue
        module = registry.module(entry.name)
        if module is not None and module.versioned:
            for inner in sorted(entry.iterdir()):
                if inner.is_dir() and f"{module.id}/{inner.name}" in keep:
                    continue
                shutil.rmtree(inner) if inner.is_dir() else inner.unlink()
        else:
            shutil.rmtree(entry)


def assemble(root: Path, registry: Registry, site_dir: str = SITE_DIR) -> list[str]:
    """Copy the built root site into the output directory.

    The available sites are already in `site_dir`/<path>/.
    Returns the paths written, relative to the output directory.
    """
    built = root / ROOT_BUILD / "site"
    if not (built / "index.html").is_file():
        raise RegistryError([f"{ROOT_BUILD}/site/ is not built: run the build of the root site first"])
    site = root / site_dir
    site.mkdir(parents=True, exist_ok=True)
    _clean(site, registry)
    written = []

    for name in ("index.html", "404.html"):
        shutil.copyfile(built / name, site / name)
        written.append(name)
    # The vendored Mermaid is not copied: no root page has a diagram.
    shutil.copytree(
        built / "assets",
        site / "assets",
        ignore=lambda directory, names: ["vendor"] if Path(directory) == built / "assets" else [],
    )
    written.append("assets/")
    for rel in root_pages(registry):
        page = rel[: -len("index.md")] + "index.html"
        source = built / page
        if not source.is_file():
            raise RegistryError([f"the root site has no page {page}"])
        (site / page).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, site / page)
        written.append(page)

    base = load_project(root / BASE_CONFIG)
    root_url = portal_root_url(base)
    for module in registry.modules:
        if module.versioned:
            data = json.dumps(versions_json(registry, module), indent=2, ensure_ascii=False) + "\n"
            (site / module.id / "versions.json").write_text(data, encoding="utf-8")
            written.append(f"{module.id}/versions.json")
    (site / "sitemap.xml").write_text(sitemap_index(registry, root_url, site), encoding="utf-8")
    written.append("sitemap.xml")
    domain = site_domain()
    if domain:
        # GitHub Pages ignores this file when the site is deployed by a
        # workflow: the custom domain is set in the settings of the
        # repository. It records the domain the portal was built for.
        (site / "CNAME").write_text(domain + "\n", encoding="utf-8")
        written.append("CNAME")
    return written


# --- command line -------------------------------------------------------------


def select(registry: Registry, name: str | None) -> list[Release]:
    """Available sites to build or check: all of them, or the one named."""
    if not name:
        return list(registry.available)
    release = registry.get(name.strip("/"))
    if release is None:
        raise RegistryError([f"`{name}` is not a site of {REGISTRY_FILE} (sites: {', '.join(registry.ids)})"])
    if not release.available:
        raise RegistryError([f"`{release.path}` is planned: it has no content to build or check"])
    return [release]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modules and releases of the portal: registry and generated files.")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="print the paths of the sites, one per line")
    listing.add_argument("--status", choices=(*STATUSES, "all"), default="all")
    commands.add_parser("default", help="print the path of the default release")
    commands.add_parser("url", help="print the address of the portal root")
    config = commands.add_parser("config", help="write the configuration of a site and print its path")
    config.add_argument("release", metavar="site")
    config.add_argument("--site-dir", default=SITE_DIR)
    commands.add_parser("root", help="write the docs and the configuration of the root site, print the path")
    assembling = commands.add_parser("assemble", help="copy the built root site into the output directory")
    assembling.add_argument("--site-dir", default=SITE_DIR)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        registry = load_registry(root)
        if args.command == "list":
            for release in registry.releases:
                if args.status in ("all", release.status):
                    print(release.path)
        elif args.command == "default":
            print(registry.default)
        elif args.command == "url":
            print(portal_root_url(load_project(root / BASE_CONFIG)))
        elif args.command == "config":
            print(os.path.relpath(write_release_config(root, registry, args.release, args.site_dir), root))
        elif args.command == "root":
            print(os.path.relpath(write_root(root, registry), root))
        elif args.command == "assemble":
            written = assemble(root, registry, args.site_dir)
            print(f"releases: root of the portal -> {args.site_dir}/ ({len(written)} entries)")
    except RegistryError as error:
        for problem in error.problems:
            print(f"releases: error: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
