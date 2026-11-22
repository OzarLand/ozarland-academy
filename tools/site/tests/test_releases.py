"""Unit tests for tools/site/releases.py (standard library only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import releases  # noqa: E402

REGISTRY = """
[[module]]
id = "lab"
step = "Discover"
title = "Quick lab"
summary = "A lab."
kind = "single"
status = "planned"

[[module]]
id = "day2"
step = "Operate"
title = "Day two"
summary = "Day-2 operations."
kind = "versioned"
default = "ussuri"

[[module.release]]
id = "ussuri"
status = "available"
openstack = "Ussuri"
kolla_ansible = "10.x"
tag = "ussuri-eol"

[[module.release]]
id = "2023.1"
status = "planned"
openstack = "2023.1 Antelope"
kolla_ansible = "16.x"

[[module]]
id = "runbooks"
step = "Intervene"
title = "Runbooks"
summary = "Runbooks."
kind = "single"
status = "available"
"""

BASE = """
[project]
site_name = "Portal"
site_url = "https://example.org/portal/"
site_description = "All modules."
repo_url = "https://github.com/example/portal"
edit_uri = "blob/main/"
extra_css = ["assets/stylesheets/portal.css"]

[project.theme]
custom_dir = "overrides"
features = ["navigation.tabs", "toc.follow", "search.highlight", "content.code.copy", "content.action.view"]

[project.extra]
generator = false

[project.markdown_extensions]
toc.permalink = true
"""

SETTINGS = """
[project]
site_description = "The Ussuri study."
nav = ["index.md", { "Operations" = ["operations/index.md", "operations/reconfigure-nova.md"] }]

[project.theme]
language = "en"
"""


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root: Path) -> None:
    write(root, "academy.toml", REGISTRY)
    write(root, "zensical.base.toml", BASE)
    write(root, "docs/day2/ussuri.toml", SETTINGS)
    write(root, "docs/day2/ussuri/index.md", "---\ntitle: Home\n---\n\n# Home\n")
    write(root, "docs/day2/ussuri/operations/index.md", "---\ntitle: Operations\n---\n\n# Operations\n")
    write(root, "docs/day2/ussuri/operations/reconfigure-nova.md", "---\ntitle: Nova\n---\n\n# Nova\n")
    write(root, "docs/day2/ussuri/assets/data/notes.md", "not a page\n")
    write(root, "docs/runbooks.toml", '[project]\nsite_description = "Runbooks."\nnav = ["index.md"]\n')
    write(root, "docs/runbooks/index.md", "---\ntitle: Runbooks\n---\n\n# Runbooks\n")


def parse(text: str) -> releases.Registry:
    return releases.parse_registry(tomllib.loads(text))


class NoDomain(unittest.TestCase):
    """SITE_DOMAIN of the environment that runs the tests is not seen, nor
    GITHUB_ACTIONS: under GitHub Actions the checks also print annotations,
    which repeat the findings that the tests count."""

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(releases.DOMAIN_VARIABLE, None)
        os.environ.pop("GITHUB_ACTIONS", None)


class RegistryTest(NoDomain):
    def test_sites_in_order_with_default_title(self) -> None:
        registry = parse(REGISTRY)
        self.assertEqual([m.id for m in registry.modules], ["lab", "day2", "runbooks"])
        self.assertEqual(registry.ids, ("lab", "day2/ussuri", "day2/2023.1", "runbooks"))
        self.assertEqual(registry.default, "day2/ussuri")
        self.assertEqual([r.path for r in registry.available], ["day2/ussuri", "runbooks"])
        self.assertEqual([r.path for r in registry.planned], ["lab", "day2/2023.1"])
        self.assertEqual(registry.get("ussuri").title, "Ussuri · Kolla-Ansible 10.x")
        self.assertEqual(registry.get("day2/2023.1").title, "2023.1 Antelope · Kolla-Ansible 16.x")
        self.assertEqual(registry.get("2023.1").docs_dir, "docs/day2/2023.1")
        self.assertEqual(registry.get("2023.1").settings_file, "docs/day2/2023.1.toml")
        self.assertEqual(registry.get("runbooks").docs_dir, "docs/runbooks")
        self.assertEqual(registry.get("runbooks").title, "Runbooks")
        self.assertEqual(registry.get("ussuri").up, "../../")
        self.assertEqual(registry.get("runbooks").up, "../")
        self.assertEqual(registry.get("day2/ussuri").config_name, "day2_ussuri")
        self.assertIsNone(registry.get("victoria"))
        self.assertEqual(registry.versioned_module.id, "day2")

    def test_explicit_title(self) -> None:
        text = REGISTRY.replace('tag = "ussuri-eol"', 'tag = "ussuri-eol"\ntitle = "Ussuri"')
        self.assertEqual(parse(text).get("ussuri").title, "Ussuri")

    def test_a_path_wins_over_a_last_segment(self) -> None:
        registry = parse(REGISTRY.replace('id = "runbooks"', 'id = "ussuri"'))
        self.assertEqual(registry.get("ussuri").path, "ussuri")  # the module, not the release
        self.assertEqual(registry.get("day2/ussuri").path, "day2/ussuri")

    def test_last_segment_must_be_unique(self) -> None:
        text = REGISTRY.replace('id = "2023.1"', 'id = "2023.1"\ntitle = "x"')
        registry = parse(text)
        self.assertEqual(registry.get("2023.1").path, "day2/2023.1")
        self.assertIsNone(registry.get("day"))

    def assert_problem(self, text: str, expected: str) -> None:
        with self.assertRaises(releases.RegistryError) as caught:
            parse(text)
        self.assertTrue(
            any(expected in problem for problem in caught.exception.problems), caught.exception.problems
        )

    def test_problems_are_reported(self) -> None:
        lab_end = 'status = "planned"\n\n[[module]]'
        release_status = 'status = "planned"\nopenstack'
        self.assert_problem("", "no [[module]] block")
        self.assert_problem(REGISTRY.replace('id = "lab"', 'id = "Lab"'), "lowercase")
        self.assert_problem(REGISTRY.replace('id = "lab"', 'id = "lab.1"'), "lowercase")
        self.assert_problem(REGISTRY.replace('id = "lab"', 'id = "assets"'), "reserved")
        self.assert_problem(REGISTRY.replace('id = "lab"', 'id = "runbooks"'), "used twice")
        self.assert_problem(REGISTRY.replace('kind = "single"\nstatus = "planned"', 'kind = "other"'), "`kind` must be")
        self.assert_problem(REGISTRY.replace(lab_end, 'status = "soon"\n\n[[module]]'), "`status` must be one of")
        self.assert_problem(REGISTRY.replace('summary = "A lab."', ""), "`summary` is missing")
        self.assert_problem(REGISTRY.replace('kind = "versioned"', 'kind = "versioned"\nstatus = "available"'), "has no `status`")
        self.assert_problem(REGISTRY.replace(lab_end, 'status = "planned"\ndefault = "x"\n\n[[module]]'), "belongs to a versioned module")
        self.assert_problem(REGISTRY.replace('id = "2023.1"', 'id = "2023/1"'), "lowercase")
        self.assert_problem(REGISTRY.replace('id = "2023.1"', 'id = "ussuri"'), "used twice")
        self.assert_problem(REGISTRY.replace(release_status, 'status = "soon"\nopenstack'), "`status` must be one of")
        self.assert_problem(REGISTRY.replace('tag = "ussuri-eol"', ""), "needs `tag`")
        self.assert_problem(REGISTRY.replace('openstack = "Ussuri"', ""), "`openstack` is missing")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "2023.1"'), "not available")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "x"'), "`default` must be")
        self.assert_problem(REGISTRY + 'date = "2027"\n', "unknown key `date`")
        self.assert_problem('latest = "x"\n' + REGISTRY, "unknown key `latest`")
        day3 = (
            '\n[[module]]\nid = "day3"\nstep = "S"\ntitle = "T"\nsummary = "S."\nkind = "versioned"\n'
            'default = "a"\n\n[[module.release]]\nid = "a"\nstatus = "available"\nopenstack = "A"\n'
            'kolla_ansible = "1.x"\ntag = "a"\n'
        )
        self.assert_problem(REGISTRY + day3, "only one module can be versioned")

    def test_prelude_is_stop_zero(self) -> None:
        registry = parse(REGISTRY)
        self.assertFalse(registry.modules[0].prelude)
        prelude = parse(REGISTRY.replace('id = "lab"', 'id = "lab"\nprelude = true', 1))
        self.assertTrue(prelude.modules[0].prelude)
        self.assert_problem(REGISTRY.replace('id = "runbooks"', 'id = "runbooks"\nprelude = true'), "only the first module")
        self.assert_problem(REGISTRY.replace('id = "lab"', 'id = "lab"\nprelude = "yes"', 1), "must be true or false")

    def test_every_problem_is_listed_at_once(self) -> None:
        text = REGISTRY.replace('tag = "ussuri-eol"', "").replace('status = "planned"\nopenstack', 'status = "soon"\nopenstack')
        with self.assertRaises(releases.RegistryError) as caught:
            parse(text)
        self.assertEqual(len(caught.exception.problems), 2)

    def test_the_registry_of_the_repository(self) -> None:
        registry = releases.load_registry(releases.ROOT)
        self.assertIn(registry.default, [r.path for r in registry.available])
        self.assertEqual(releases.layout_problems(releases.ROOT, registry), [])
        for release in registry.planned:
            self.assertFalse((releases.ROOT / release.docs_dir).exists(), release.path)

    def test_readme_lists_the_available_releases(self) -> None:
        registry = releases.load_registry(releases.ROOT)
        module = registry.versioned_module
        readme = (releases.ROOT / "README.md").read_text(encoding="utf-8")
        heading = f"## {module.step}: {module.title} (`{module.id}`)"
        self.assertIn(heading, readme)
        section = readme.split(heading, 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
        listed = {}
        for row in section.splitlines():
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if row.startswith("| `") and len(cells) >= 2:
                listed[cells[0].strip("`")] = cells[1]
        self.assertEqual(
            listed,
            {release.id: release.openstack for release in module.releases if release.available},
            "the table of the day-2 section of README.md does not list the available releases of academy.toml",
        )


class AddressTest(NoDomain):
    def test_default_and_domain(self) -> None:
        base = {"site_url": "https://example.org/portal"}
        self.assertEqual(releases.portal_root_url(base), "https://example.org/portal/")
        self.assertEqual(releases.portal_root_url(base, {"SITE_DOMAIN": ""}), "https://example.org/portal/")
        self.assertEqual(
            releases.portal_root_url(base, {"SITE_DOMAIN": " Academy.Example.org. "}), "https://academy.example.org/"
        )
        os.environ["SITE_DOMAIN"] = "academy.example.org"
        self.assertEqual(releases.portal_root_url(base), "https://academy.example.org/")

    def test_bad_domain(self) -> None:
        for value in ("https://academy.example.org", "academy.example.org/x", "academy.example.org:8080", "localhost"):
            with self.assertRaises(releases.RegistryError, msg=value):
                releases.portal_root_url({"site_url": "https://example.org/"}, {"SITE_DOMAIN": value})

    def test_missing_site_url(self) -> None:
        with self.assertRaises(releases.RegistryError):
            releases.portal_root_url({})


class RepoTest(NoDomain):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        make_repo(self.root)
        self.registry = releases.load_registry(self.root)


class LayoutTest(RepoTest):
    def test_consistent_tree(self) -> None:
        self.assertEqual(releases.layout_problems(self.root, self.registry), [])

    def test_differences(self) -> None:
        write(self.root, "docs/day2/2023.1/index.md", "# Home\n")  # planned, with content
        write(self.root, "docs/day2/victoria/index.md", "# Home\n")  # not registered
        write(self.root, "docs/day2/victoria.toml", "[project]\n")
        write(self.root, "docs/day2/index.md", "# Stray\n")
        write(self.root, "docs/day2.toml", "[project]\n")
        write(self.root, "docs/lab/index.md", "# Planned\n")
        write(self.root, "docs/other/index.md", "# Unknown\n")
        write(self.root, "docs/index.md", "# Stray\n")
        (self.root / "docs/day2/ussuri.toml").unlink()
        (self.root / "docs/runbooks.toml").unlink()
        problems = "\n".join(releases.layout_problems(self.root, self.registry))
        self.assertIn("release `day2/2023.1` is planned but docs/day2/2023.1/ exists", problems)
        self.assertIn("docs/day2/victoria/ is not a release", problems)
        self.assertIn("docs/day2/victoria.toml does not belong to a release", problems)
        self.assertIn("docs/day2/index.md: files belong to the directory of a site", problems)
        self.assertIn("docs/day2.toml: a versioned module has one settings file per release", problems)
        self.assertIn("module `lab` is planned but docs/lab/ exists", problems)
        self.assertIn("docs/other/ is not a module", problems)
        self.assertIn("docs/index.md: files belong to the directory of a site", problems)
        self.assertIn("release `day2/ussuri` is available but docs/day2/ussuri.toml does not exist", problems)
        self.assertIn("module `runbooks` is available but docs/runbooks.toml does not exist", problems)


class ConfigTest(RepoTest):
    def test_release_configuration(self) -> None:
        project = releases.release_project(self.root, self.registry, "day2/ussuri")
        self.assertEqual(project["docs_dir"], "docs/day2/ussuri")
        self.assertEqual(project["site_dir"], "site/day2/ussuri")
        self.assertEqual(project["site_url"], "https://example.org/portal/day2/ussuri/")
        self.assertEqual(project["edit_uri"], "blob/main/docs/day2/ussuri/")
        self.assertEqual(project["site_description"], "The Ussuri study.")  # of the release
        self.assertEqual(project["site_name"], "Day two")  # the title of the module
        # Tables are merged, lists are replaced.
        self.assertEqual(project["theme"]["custom_dir"], "overrides")
        self.assertEqual(project["theme"]["language"], "en")
        self.assertEqual(project["nav"][0], "index.md")
        portal = project["extra"]["portal"]
        self.assertFalse(project["extra"]["generator"])
        self.assertEqual(
            (portal["kind"], portal["current"], portal["path"], portal["up"]),
            ("release", "ussuri", "day2/ussuri", "../../"),
        )
        self.assertEqual(portal["root_url"], "https://example.org/portal/")
        self.assertEqual(portal["root_path"], "/portal/")
        self.assertEqual(portal["default"], "day2/ussuri")
        self.assertEqual(portal["module"]["id"], "day2")
        self.assertEqual([r["path"] for r in portal["releases"]], ["day2/ussuri", "day2/2023.1"])
        self.assertEqual(portal["releases"][1]["status"], "planned")
        self.assertEqual([m["id"] for m in portal["modules"]], ["lab", "day2", "runbooks"])
        self.assertEqual([m["status"] for m in portal["modules"]], ["planned", "available", "available"])
        self.assertEqual([s["path"] for s in portal["sites"]], list(self.registry.ids))

    def test_single_module_configuration(self) -> None:
        project = releases.release_project(self.root, self.registry, "runbooks")
        self.assertEqual(project["docs_dir"], "docs/runbooks")
        self.assertEqual(project["site_dir"], "site/runbooks")
        self.assertEqual(project["site_url"], "https://example.org/portal/runbooks/")
        self.assertEqual(project["site_name"], "Runbooks")
        portal = project["extra"]["portal"]
        self.assertEqual((portal["current"], portal["path"], portal["up"]), ("runbooks", "runbooks", "../"))
        self.assertEqual([r["path"] for r in portal["releases"]], ["runbooks"])
        self.assertEqual(portal["module"]["kind"], "single")
        self.assertNotIn("journey", project["extra"])

    def test_domain_sets_every_address(self) -> None:
        os.environ["SITE_DOMAIN"] = "academy.example.org"
        project = releases.release_project(self.root, self.registry, "day2/ussuri")
        self.assertEqual(project["site_url"], "https://academy.example.org/day2/ussuri/")
        self.assertEqual(project["extra"]["portal"]["root_url"], "https://academy.example.org/")
        self.assertEqual(project["extra"]["portal"]["root_path"], "/")
        self.assertEqual(releases.root_project(self.root, self.registry)["site_url"], "https://academy.example.org/")

    def test_release_may_override_edit_uri_and_site_name(self) -> None:
        write(self.root, "docs/day2/ussuri.toml", SETTINGS.replace("nav =", 'site_name = "U"\nedit_uri = "edit/x/"\nnav ='))
        project = releases.release_project(self.root, self.registry, "ussuri")
        self.assertEqual((project["site_name"], project["edit_uri"]), ("U", "edit/x/"))

    def test_derived_keys_are_refused(self) -> None:
        for key, value in (("docs_dir", '"docs"'), ("site_url", '"https://u.example/"')):
            write(self.root, "docs/day2/ussuri.toml", SETTINGS.replace("nav =", f"{key} = {value}\nnav ="))
            with self.assertRaises(releases.RegistryError) as caught:
                releases.release_project(self.root, self.registry, "ussuri")
            self.assertIn(f"`{key}` is set by the tooling", str(caught.exception))

    def test_planned_or_unknown_site_has_no_configuration(self) -> None:
        for name in ("2023.1", "lab", "victoria"):
            with self.assertRaises(releases.RegistryError):
                releases.release_project(self.root, self.registry, name)
        with self.assertRaises(releases.RegistryError):
            releases.select(self.registry, "day2/2023.1")
        self.assertEqual([r.path for r in releases.select(self.registry, None)], ["day2/ussuri", "runbooks"])
        self.assertEqual([r.path for r in releases.select(self.registry, "day2/ussuri/")], ["day2/ussuri"])

    def test_written_configuration_reads_back(self) -> None:
        path = releases.write_release_config(self.root, self.registry, "day2/ussuri")
        self.assertEqual(path, self.root / ".zensical.day2_ussuri.toml")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Generated by tools/site/releases.py"))
        self.assertEqual(
            tomllib.loads(text)["project"], releases.release_project(self.root, self.registry, "day2/ussuri")
        )
        stamp = path.stat().st_mtime_ns
        releases.write_release_config(self.root, self.registry, "day2/ussuri")
        self.assertEqual(path.stat().st_mtime_ns, stamp)  # not rewritten

    def test_toml_writer(self) -> None:
        project = {
            "text": 'quote " backslash \\ tab \t line\nbreak · é \x7f',
            "flag": True,
            "off": False,
            "number": 3,
            "ratio": 0.5,
            "empty": [],
            "table": {"a.b": {"c": [1, {"d": "e"}]}, "nothing": {}},
            "list": ["x", {"Title": ["a.md", {"Sub": "b.md"}]}],
        }
        self.assertEqual(tomllib.loads(releases.dump_toml(project, "note"))["project"], project)
        with self.assertRaises(TypeError):
            releases.dump_toml({"when": object()})

    def test_page_urls(self) -> None:
        self.assertEqual(
            releases.page_urls(self.root, self.registry.get("ussuri")),
            ["", "operations/", "operations/reconfigure-nova/"],
        )


class RootTest(RepoTest):
    def test_root_configuration_and_stubs(self) -> None:
        path = releases.write_root(self.root, self.registry)
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        self.assertEqual(path.name, ".zensical._root.toml")
        self.assertEqual(project["docs_dir"], ".build/root/docs")
        self.assertEqual(project["site_dir"], ".build/root/site")
        self.assertEqual(project["site_url"], "https://example.org/portal/")
        self.assertEqual(project["nav"], ["index.md", "lab/index.md", "day2/index.md", "day2/2023.1/index.md"])
        self.assertNotIn("edit_uri", project)
        self.assertEqual(project["theme"]["features"], ["content.code.copy"])
        portal = project["extra"]["portal"]
        self.assertEqual((portal["kind"], portal["current"], portal["up"]), ("root", "", ""))
        self.assertEqual([r["id"] for r in portal["releases"]], ["ussuri", "2023.1"])
        self.assertNotIn("unprefixed", portal)
        docs = self.root / ".build/root/docs"
        self.assertEqual(
            sorted(p.relative_to(docs).as_posix() for p in docs.rglob("*.md")),
            ["day2/2023.1/index.md", "day2/index.md", "index.md", "lab/index.md"],
        )
        stub = (docs / "day2/2023.1/index.md").read_text(encoding="utf-8")
        self.assertIn('template: "planned.html"', stub)
        self.assertIn('portal_release: "2023.1"', stub)
        self.assertIn('portal_module: "day2"', stub)
        self.assertIn("# 2023.1 Antelope · Kolla-Ansible 16.x", stub)
        stub = (docs / "lab/index.md").read_text(encoding="utf-8")
        self.assertIn('template: "planned.html"', stub)
        self.assertIn('portal_module: "lab"', stub)
        self.assertNotIn("portal_release", stub)
        self.assertIn('template: "landing.html"', (docs / "day2/index.md").read_text(encoding="utf-8"))
        self.assertIn('template: "academy.html"', (docs / "index.md").read_text(encoding="utf-8"))

    def test_stub_of_a_release_that_is_no_longer_planned_is_removed(self) -> None:
        releases.write_root(self.root, self.registry)
        available = REGISTRY.replace('status = "planned"\nopenstack', 'status = "available"\ntag = "t"\nopenstack')
        write(self.root, "academy.toml", available)
        releases.write_root(self.root, releases.load_registry(self.root))
        self.assertFalse((self.root / ".build/root/docs/day2/2023.1").exists())

    def fake_root_build(self) -> None:
        for rel in ("index.html", "404.html", "lab/index.html", "day2/index.html", "day2/2023.1/index.html",
                    "assets/stylesheets/portal.css", "assets/vendor/mermaid/mermaid.min.js", "search.json",
                    "sitemap.xml"):
            write(self.root, f".build/root/site/{rel}", rel)

    def built_files(self) -> list[str]:
        site = self.root / "site"
        return sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())

    def test_assemble(self) -> None:
        self.fake_root_build()
        write(self.root, "site/day2/ussuri/index.html", "ussuri")
        write(self.root, "site/day2/ussuri/sitemap.xml", "<urlset/>")
        write(self.root, "site/runbooks/index.html", "runbooks")
        write(self.root, "site/day2/victoria/index.html", "left by an earlier build")
        write(self.root, "site/day2/2023.1/old/index.html", "left by an earlier build")
        write(self.root, "site/day2/stale.txt", "left by an earlier build")
        write(self.root, "site/ussuri/index.html", "left by an earlier build")
        write(self.root, "site/stale.txt", "left by an earlier build")
        releases.assemble(self.root, self.registry)
        self.assertEqual(
            self.built_files(),
            [
                "404.html",
                "assets/stylesheets/portal.css",
                "day2/2023.1/index.html",
                "day2/index.html",
                "day2/ussuri/index.html",
                "day2/ussuri/sitemap.xml",
                "day2/versions.json",
                "index.html",
                "lab/index.html",
                "robots.txt",
                "runbooks/index.html",
                "sitemap-portal.xml",
                "sitemap.xml",
            ],
        )
        site = self.root / "site"
        module = self.registry.versioned_module
        versions = json.loads((site / "day2/versions.json").read_text(encoding="utf-8"))
        self.assertEqual(versions, releases.versions_json(self.registry, module))
        self.assertEqual([v["version"] for v in versions], ["ussuri", "2023.1"])
        self.assertEqual(versions[0]["title"], "Ussuri · Kolla-Ansible 10.x")
        self.assertEqual(versions[0]["aliases"], [])
        self.assertEqual(
            versions[0]["properties"],
            {"status": "available", "default": True, "openstack": "Ussuri", "kolla_ansible": "10.x", "tag": "ussuri-eol"},
        )
        self.assertEqual(versions[1]["properties"]["status"], "planned")
        sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://example.org/portal/day2/ussuri/sitemap.xml</loc>", sitemap)
        self.assertNotIn("2023.1", sitemap)
        self.assertIn("<loc>https://example.org/portal/sitemap-portal.xml</loc>", sitemap)
        portal = (site / "sitemap-portal.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://example.org/portal/</loc>", portal)
        self.assertIn("<loc>https://example.org/portal/day2/</loc>", portal)
        self.assertNotIn("2023.1", portal)
        robots = (site / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Sitemap: https://example.org/portal/sitemap.xml", robots)

    def test_assemble_writes_cname_for_a_domain(self) -> None:
        self.fake_root_build()
        releases.assemble(self.root, self.registry)
        self.assertFalse((self.root / "site/CNAME").exists())
        os.environ["SITE_DOMAIN"] = "academy.example.org"
        releases.assemble(self.root, self.registry)
        self.assertEqual((self.root / "site/CNAME").read_text(encoding="utf-8"), "academy.example.org\n")
        os.environ.pop("SITE_DOMAIN")
        releases.assemble(self.root, self.registry)
        self.assertFalse((self.root / "site/CNAME").exists())  # left by the earlier build

    def test_assemble_needs_the_root_build(self) -> None:
        with self.assertRaises(releases.RegistryError):
            releases.assemble(self.root, self.registry)


class CommandLineTest(RepoTest):
    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = releases.main(["--root", str(self.root), *args])
        return status, out.getvalue(), err.getvalue()

    def test_commands(self) -> None:
        self.assertEqual(self.run_main("list")[1].split(), ["lab", "day2/ussuri", "day2/2023.1", "runbooks"])
        self.assertEqual(self.run_main("list", "--status", "available")[1].split(), ["day2/ussuri", "runbooks"])
        self.assertEqual(self.run_main("list", "--status", "planned")[1].split(), ["lab", "day2/2023.1"])
        self.assertEqual(self.run_main("default")[1].strip(), "day2/ussuri")
        self.assertEqual(self.run_main("url")[1].strip(), "https://example.org/portal/")
        self.assertEqual(self.run_main("config", "ussuri")[1].strip(), ".zensical.day2_ussuri.toml")
        self.assertEqual(self.run_main("config", "runbooks")[1].strip(), ".zensical.runbooks.toml")
        self.assertEqual(self.run_main("root")[1].strip(), ".zensical._root.toml")
        status, _, err = self.run_main("config", "day2/2023.1")
        self.assertEqual(status, 1)
        self.assertIn("planned", err)

    def test_bad_domain(self) -> None:
        os.environ["SITE_DOMAIN"] = "https://academy.example.org/"
        status, _, err = self.run_main("url")
        self.assertEqual(status, 1)
        self.assertIn("SITE_DOMAIN", err)

    def test_unreadable_registry(self) -> None:
        write(self.root, "academy.toml", "[[module]")
        status, _, err = self.run_main("list")
        self.assertEqual(status, 1)
        self.assertIn("cannot be read", err)


if __name__ == "__main__":
    unittest.main()
