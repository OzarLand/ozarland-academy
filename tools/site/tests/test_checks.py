"""Unit tests for what check_docs.py and check_site.py check about modules and releases.

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import html
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs  # noqa: E402
import check_site  # noqa: E402
import releases  # noqa: E402
from test_releases import REGISTRY, NoDomain, make_repo, write  # noqa: E402

PORTAL = "https://example.org/portal/"

PAGE = """---
title: {title}
description: A page.
---

# {title}

## Details

{body}
"""

WALLABY = """
[[module.release]]
id = "wallaby"
status = "available"
openstack = "Wallaby"
kolla_ansible = "12.x"
tag = "wallaby-eol"

"""

#: The block of the last module, before which a release of day2 is added.
RUNBOOKS = '[[module]]\nid = "runbooks"'


def page(title: str, body: str = "Text.") -> str:
    return PAGE.format(title=title, body=body)


def run(module, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = module.main(list(args))
    return status, out.getvalue()


class Repo(NoDomain):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        make_repo(self.root)
        write(self.root, "docs/day2/ussuri/index.md", page("Home", "[Operations](operations/index.md)"))
        write(self.root, "docs/day2/ussuri/operations/index.md", page("Operations", "[Nova](reconfigure-nova.md#details)"))
        write(self.root, "docs/day2/ussuri/operations/reconfigure-nova.md", page("Nova"))
        write(self.root, "docs/runbooks/index.md", page("Runbooks"))
        (self.root / "docs/day2/ussuri/assets/data/notes.md").unlink()

    def add_wallaby(self) -> None:
        write(self.root, "academy.toml", REGISTRY.replace(RUNBOOKS, WALLABY + RUNBOOKS))
        write(self.root, "docs/day2/wallaby.toml", '[project]\nnav = ["index.md"]\n')
        write(self.root, "docs/day2/wallaby/index.md", page("Home"))


class CheckDocsTest(Repo):
    def check(self, *args: str) -> tuple[int, str]:
        return run(check_docs, "--root", str(self.root), *args)

    def test_consistent_repository(self) -> None:
        status, out = self.check("--strict")
        self.assertEqual(status, 0, out)
        self.assertIn("Sites checked (pages): day2/ussuri (3), runbooks (1). Planned, no content: lab, day2/2023.1.", out)
        self.assertIn(f"Address of the portal: {PORTAL}", out)

    def test_every_available_site_is_checked(self) -> None:
        self.add_wallaby()
        write(self.root, "docs/day2/wallaby/extra.md", page("Not in the nav"))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("docs/day2/wallaby/extra.md", out)
        self.assertIn("page is not listed in the nav of docs/day2/wallaby.toml", out)
        self.assertIn("day2/ussuri (3), day2/wallaby (2), runbooks (1)", out)
        # One site only: the other ones are not read.
        status, out = self.check("--release", "day2/ussuri")
        self.assertEqual(status, 0, out)
        self.assertEqual(self.check("--release", "2023.1")[0], 1)  # planned: nothing to check

    def test_registry_and_tree_must_agree(self) -> None:
        write(self.root, "docs/day2/2023.1/index.md", page("Home"))
        write(self.root, "docs/day2/yoga/index.md", page("Home"))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("registry", out)
        self.assertIn("`day2/2023.1` is planned but docs/day2/2023.1/ exists", out)
        self.assertIn("docs/day2/yoga/ is not a release of academy.toml", out)

    def test_unreadable_registry(self) -> None:
        write(self.root, "academy.toml", REGISTRY.replace('default = "ussuri"', 'default = "nope"'))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("`default` must be the id of one of its releases", out)

    def test_nav_entry_that_does_not_exist(self) -> None:
        nav = '[project]\nnav = ["index.md", "operations/index.md", "operations/reconfigure-nova.md", "gone.md"]\n'
        write(self.root, "docs/day2/ussuri.toml", nav)
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("docs/day2/ussuri.toml", out)
        self.assertIn("nav entry `gone.md` does not exist under docs/day2/ussuri/", out)

    def link(self, target: str) -> str:
        """Findings for one link from the home page of the release wallaby."""
        self.add_wallaby()
        write(self.root, "docs/day2/wallaby/index.md", page("Home", f"[there]({target})"))
        return self.check()[1]

    # -- links to another site --------------------------------------------------

    def test_link_to_a_file_of_another_site_is_refused(self) -> None:
        out = self.link("../ussuri/operations/reconfigure-nova.md")
        self.assertIn("link-site", out)
        self.assertIn("is a file of another site (docs/day2/ussuri/)", out)
        self.assertIn("../ussuri/operations/reconfigure-nova/", out)
        out = self.link("../../runbooks/index.md")
        self.assertIn("is a file of another site (docs/runbooks/)", out)
        self.assertIn("../../runbooks/", out)

    def test_relative_address_of_a_page_of_another_site_is_accepted(self) -> None:
        for target in (
            "../../",  # the learning path
            "../",  # the home of the day-2 module
            "../ussuri/",
            "../ussuri/operations/",
            "../ussuri/operations/reconfigure-nova/",
            "../ussuri/operations/reconfigure-nova/#details",
            "../2023.1/",  # planned: its only page
            "../../lab/",  # planned module
            "../../runbooks/",
        ):
            with self.subTest(target=target):
                self.assertIn("check_docs: OK", self.link(target))

    def test_relative_address_that_leads_nowhere_is_reported(self) -> None:
        out = self.link("../ussuri/operations/reconfigure-neutron/")
        self.assertIn("`day2/ussuri` has no page `operations/reconfigure-neutron`", out)
        out = self.link("../ussuri/operations/reconfigure-nova/#nowhere")
        self.assertIn("`#nowhere` is not an anchor of docs/day2/ussuri/operations/reconfigure-nova.md", out)
        out = self.link("../victoria/")
        self.assertIn("is not a page of the portal", out)
        out = self.link("../2023.1/operations/")
        self.assertIn("`day2/2023.1` is planned and has no page other than its home", out)
        out = self.link("../../lab/setup/")
        self.assertIn("`lab` is planned and has no page other than its home", out)

    def test_address_inside_the_same_site_is_refused(self) -> None:
        out = self.link("../wallaby/")
        self.assertIn("is a page of this site: link to its .md file", out)

    # -- addresses of the portal --------------------------------------------------

    def test_address_of_the_portal_in_a_page_is_refused(self) -> None:
        for target in (PORTAL, f"{PORTAL}day2/ussuri/", "http://example.org/portal/runbooks/"):
            with self.subTest(target=target):
                out = self.link(target)
                self.assertIn("link-site-address", out)
                self.assertIn("is an address of the portal: use a relative link", out)

    def test_former_address_and_plain_text_are_refused(self) -> None:
        self.add_wallaby()
        body = "See https://ozarland.github.io/kolla-ansible-academy/ussuri/ or <https://example.org/portal/>."
        write(self.root, "docs/day2/wallaby/index.md", page("Home", body))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertEqual(out.count("link-site-address"), 3, out)  # two findings and the summary

    def test_address_in_code_is_not_a_link(self) -> None:
        self.add_wallaby()
        body = "Run `curl https://example.org/portal/day2/` or:\n\n```bash\ncurl https://example.org/portal/\n```"
        write(self.root, "docs/day2/wallaby/index.md", page("Home", body))
        status, out = self.check()
        self.assertEqual(status, 0, out)

    def test_readme_may_write_the_current_address_only(self) -> None:
        write(self.root, "README.md", f"# Portal\n\n<{PORTAL}>\n")
        status, out = self.check()
        self.assertEqual(status, 0, out)
        write(self.root, "README.md", "# Portal\n\n<https://ozarland.github.io/kolla-ansible-academy/>\n")
        status, out = self.check()
        self.assertIn("is not the current address of the portal", out)
        os.environ["SITE_DOMAIN"] = "academy.example.org"
        write(self.root, "README.md", f"# Portal\n\n<{PORTAL}>\n")
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("is not the current address of the portal (https://academy.example.org/)", out)
        write(self.root, "README.md", "# Portal\n\n<https://academy.example.org/>\n")
        status, out = self.check()
        self.assertEqual(status, 0, out)

    def test_domain_address_in_a_page_is_refused(self) -> None:
        os.environ["SITE_DOMAIN"] = "academy.example.org"
        out = self.link("https://academy.example.org/day2/ussuri/")
        self.assertIn("is an address of the portal: use a relative link", out)


def html_page(title: str, body: str = "<p>Text.</p>", head: str = "", canonical: str = "") -> str:
    link = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return (
        f"<!doctype html><html><head><title>{title}</title>{link}{head}</head>"
        f"<body><main><article><h1>{title}</h1>{body}</article></main></body></html>"
    )


class CheckSiteTest(Repo):
    """A hand-made portal: one release and one module available, a planned release and module, the root."""

    def setUp(self) -> None:
        super().setUp()
        self.registry = releases.load_registry(self.root)
        self.build()

    def build_site(self, path: str, pages: dict[str, str], link: str) -> None:
        site = "site/"
        for url, title in pages.items():
            up = "../" * (url.count("/") + path.count("/") + 1)
            body = f'<p>Text.</p><a href="{up}{link}">Elsewhere</a>'
            write(self.root, f"{site}{path}/{url}index.html", html_page(title, body, canonical=f"{PORTAL}{path}/{url}"))
        write(self.root, f"{site}{path}/search.json", json.dumps({"items": [{"location": url} for url in pages]}))
        locs = "".join(f"<url><loc>{PORTAL}{path}/{url}</loc></url>" for url in pages)
        write(self.root, f"{site}{path}/sitemap.xml", f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
        write(self.root, f"{site}{path}/assets/data/updates.json", json.dumps({"pages": [{"url": url} for url in pages]}))

    def build(self) -> None:
        registry = releases.load_registry(self.root)
        site = "site/"
        self.build_site("day2/ussuri", {"": "Home", "operations/": "Operations", "operations/reconfigure-nova/": "Nova"}, "day2/2023.1/")
        self.build_site("runbooks", {"": "Runbooks"}, "day2/ussuri/")
        steps = "".join(
            f'<a href="{m.id}/" data-portal-module="{m.id}">{html.escape(m.title)}</a>' for m in registry.modules
        )
        write(self.root, f"{site}index.html", html_page("Portal", steps + '<a href="day2/" data-portal-start="day2">Start</a>'))
        lists = "".join(f'<a href="../{r.path}/">{html.escape(r.title)}</a>' for r in registry.releases if r.versioned)
        write(self.root, f"{site}day2/index.html", html_page("Day two", lists + '<a href="ussuri/" data-portal-default="day2/ussuri">Go</a>'))
        data = {"root_url": PORTAL, "sites": [r.as_dict() for r in registry.releases]}
        script = f'<script id="portal-not-found" type="application/json">{json.dumps(data)}</script>'
        write(self.root, f"{site}404.html", html_page("Page not found", '<a href="/portal/day2/ussuri/">Ussuri</a>', head=script))
        for release in registry.planned:
            up = "../" * (release.path.count("/") + 1)
            body = f'<p>Coming soon: not available yet.</p><a href="{up}day2/ussuri/">Ussuri</a>'
            write(self.root, f"{site}{release.path}/index.html", html_page(html.escape(release.title), body))
        module = registry.versioned_module
        write(self.root, f"{site}day2/versions.json", json.dumps(releases.versions_json(registry, module)))
        write(self.root, f"{site}sitemap.xml", releases.sitemap_index(registry, PORTAL, self.root / "site"))

    def check(self, *args: str) -> tuple[int, str]:
        return run(check_site, str(self.root / "site"), "--root", str(self.root), *args)

    def test_consistent_portal(self) -> None:
        status, out = self.check("--strict")
        self.assertEqual(status, 0, out)
        self.assertIn("Site day2/ussuri: 3 of 3 Markdown page(s) of docs/day2/ussuri/ are built", out)
        self.assertIn("Site runbooks: 1 of 1 Markdown page(s) of docs/runbooks/ are built", out)
        self.assertIn("planned modules and releases with their page: lab, day2/2023.1", out)

    def expect(self, *messages: str) -> str:
        status, out = self.check()
        self.assertEqual(status, 1, out)
        for message in messages:
            self.assertIn(message, out)
        return out

    def test_versions_json_must_match_the_registry(self) -> None:
        module = self.registry.versioned_module
        write(self.root, "site/day2/versions.json", json.dumps(releases.versions_json(self.registry, module)[:1]))
        self.expect("portal-root", "day2/versions.json", "does not match academy.toml")
        write(self.root, "site/day2/versions.json", "{")
        self.expect("not valid JSON")
        (self.root / "site/day2/versions.json").unlink()
        self.expect("the file is missing")

    def test_learning_path_lists_the_modules(self) -> None:
        text = (self.root / "site/index.html").read_text(encoding="utf-8")
        write(self.root, "site/index.html", text.replace('data-portal-module="lab"', ""))
        self.expect("the learning path lists ['day2', 'runbooks']")
        write(self.root, "site/index.html", text.replace('data-portal-start="day2"', 'data-portal-start="lab"'))
        self.expect("the call to action does not open the first available module `day2`")

    def test_home_of_the_module_opens_the_default_release(self) -> None:
        text = (self.root / "site/day2/index.html").read_text(encoding="utf-8")
        write(self.root, "site/day2/index.html", text.replace('data-portal-default="day2/ussuri"', 'data-portal-default="day2/2023.1"'))
        self.expect("the home of the module links to `day2/2023.1`, the default release is `day2/ussuri`")

    def test_sites_of_the_not_found_page(self) -> None:
        path = self.root / "site/404.html"
        text = path.read_text(encoding="utf-8")
        write(self.root, "site/404.html", text.replace('"status": "planned"', '"status": "available"'))
        self.expect("the sites it knows do not match academy.toml")
        write(self.root, "site/404.html", html_page("Page not found"))
        self.expect("script #portal-not-found")

    def test_planned_release_has_one_page_that_says_so(self) -> None:
        write(self.root, "site/day2/2023.1/operations/index.html", html_page("Operations"))
        self.expect("a planned module or release has one page only, found also: day2/2023.1/operations/index.html")
        (self.root / "site/day2/2023.1/operations/index.html").unlink()
        write(self.root, "site/day2/2023.1/index.html", html_page("Something else"))
        self.expect("does not name the module or release, or does not say that it is not available yet")
        (self.root / "site/day2/2023.1/index.html").unlink()
        self.expect("the page of the planned `day2/2023.1` is missing", "is not in the site")

    def test_planned_module_has_its_page(self) -> None:
        (self.root / "site/lab/index.html").unlink()
        self.expect("the page of the planned `lab` is missing")

    def test_available_release_must_be_built(self) -> None:
        self.add_wallaby()
        self.build()
        out = self.expect("`day2/wallaby` is available but its site is not built")
        self.assertIn("page-missing", out)
        # Built alone, a site may link to sites that this run did not build.
        status, out = self.check("--release", "day2/ussuri")
        self.assertEqual(status, 0, out)
        self.assertIn("Not built in this run", out)

    def test_directory_of_no_site(self) -> None:
        write(self.root, "site/victoria/index.html", html_page("Victoria"))
        self.expect("victoria/", "directory of no module of academy.toml")
        (self.root / "site/victoria/index.html").unlink()
        (self.root / "site/victoria").rmdir()
        write(self.root, "site/day2/victoria/index.html", html_page("Victoria"))
        self.expect("day2/victoria/", "directory of no release of the module `day2`")

    def test_links_between_sites_are_checked(self) -> None:
        text = (self.root / "site/day2/ussuri/index.html").read_text(encoding="utf-8")
        write(self.root, "site/day2/ussuri/index.html", text.replace('href="../../day2/2023.1/"', 'href="../../day2/zed/"'))
        self.expect("link-file", "`day2/zed/index.html` is not in the site")

    def test_search_index_and_sitemap_stay_inside_the_site(self) -> None:
        write(self.root, "site/day2/ussuri/search.json", json.dumps({"items": [{"location": "../2023.1/"}]}))
        self.expect("search-index", "which is not in the site", "page has no entry in day2/ussuri/search.json")
        (self.root / "site/day2/ussuri/search.json").unlink()
        self.expect("day2/ussuri/search.json", "the search index file is missing")

    def test_canonical_address(self) -> None:
        text = (self.root / "site/day2/ussuri/operations/index.html").read_text(encoding="utf-8")
        write(
            self.root,
            "site/day2/ussuri/operations/index.html",
            text.replace(f"{PORTAL}day2/ussuri/operations/", f"{PORTAL}ussuri/operations/"),
        )
        self.expect("canonical", "is not the address of this page")

    def test_page_without_built_file(self) -> None:
        write(self.root, "docs/day2/ussuri/operations/new.md", page("New"))
        self.expect("page-missing", "docs/day2/ussuri/operations/new.md")


if __name__ == "__main__":
    unittest.main()
