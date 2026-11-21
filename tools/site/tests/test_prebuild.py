"""Unit tests for tools/site/prebuild.py (standard library and git only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "prebuild", Path(__file__).resolve().parents[1] / "prebuild.py"
)
prebuild = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prebuild)


def git(root: Path, *args: str, date: str | None = None) -> None:
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.org",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.org",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
    )
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        check=True,
        capture_output=True,
        env=env,
    )


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(root: Path) -> dict:
    # --skip-vendor: these tests are about updates.json and must not download.
    assert prebuild.main(["--root", str(root), "--docs-dir", "docs", "--skip-vendor"]) == 0
    return json.loads((root / "docs/assets/data/updates.json").read_text(encoding="utf-8"))


class PrebuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        write(self.repo, "docs/index.md", "---\ntitle: Home\n---\n\n# Home\n")
        write(
            self.repo,
            "docs/operations/reconfigure-nova.md",
            "---\ntitle: Reconfigure Nova\ntags: [nova]\n---\n\n# Reconfigure Nova\n",
        )
        write(self.repo, "docs/operations/index.md", "# Operations\n")
        write(self.repo, "docs/assets/notes/README.md", "# Not a page\n")
        write(self.repo, "docs/reference/listings/list.txt", "not a page\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "zero", date="2024-03-01T10:00:00+00:00")
        write(self.repo, "docs/operations/index.md", "# Operations\n\nHub.\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "one", date="2024-04-10T09:00:00+00:00")
        write(
            self.repo,
            "docs/operations/reconfigure-nova.md",
            "---\ntitle: 'Reconfigure Nova: computes'\n---\n\n# Reconfigure Nova\n\nMore.\n",
        )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "two", date="2024-05-17T23:30:00+02:00")
        write(self.repo, "README.md", "outside docs\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "three", date="2024-06-02T08:00:00+00:00")

    def test_dates_titles_and_urls(self) -> None:
        data = run(self.repo)
        self.assertEqual(data["generated"], "2024-06-02T08:00:00+00:00")
        self.assertEqual(
            data["pages"],
            [
                {"path": "index.md", "url": "", "title": "Home", "updated": "2024-03-01"},
                {
                    "path": "operations/index.md",
                    "url": "operations/",
                    "title": "Operations",
                    "updated": "2024-04-10",
                },
                {
                    "path": "operations/reconfigure-nova.md",
                    "url": "operations/reconfigure-nova/",
                    "title": "Reconfigure Nova: computes",
                    "updated": "2024-05-17",
                },
            ],
        )

    def test_excluded_docs_are_not_pages(self) -> None:
        write(self.repo, "docs.toml", '[project]\nexclude_docs = """\n/operations/\n!/operations/index.md\n"""\n')
        paths = [p["path"] for p in run(self.repo)["pages"]]
        self.assertEqual(paths, ["index.md", "operations/index.md"])

    def test_same_commit_gives_the_same_file(self) -> None:
        first = run(self.repo)
        output = self.repo / "docs/assets/data/updates.json"
        stamp = output.stat().st_mtime_ns
        self.assertEqual(run(self.repo), first)
        self.assertEqual(output.stat().st_mtime_ns, stamp)  # not rewritten

    def test_uncommitted_page_gets_the_head_date(self) -> None:
        write(self.repo, "docs/new-page.md", "# A `new` page\n")
        page = next(p for p in run(self.repo)["pages"] if p["path"] == "new-page.md")
        self.assertEqual(page, {
            "path": "new-page.md", "url": "new-page/", "title": "A new page", "updated": "2024-06-02",
        })

    def test_shallow_clone_falls_back_to_the_head_date(self) -> None:
        shallow = Path(self._tmp.name) / "shallow"
        git(Path(self._tmp.name), "clone", "-q", "--depth", "1", self.repo.as_uri(), str(shallow))
        data = run(shallow)
        self.assertEqual(data["generated"], "2024-06-02T08:00:00+00:00")
        self.assertEqual({p["updated"] for p in data["pages"]}, {"2024-06-02"})
        self.assertEqual(len(data["pages"]), 3)

    def test_shallow_clone_keeps_dates_inside_the_fetched_history(self) -> None:
        shallow = Path(self._tmp.name) / "shallow3"
        git(Path(self._tmp.name), "clone", "-q", "--depth", "3", self.repo.as_uri(), str(shallow))
        pages = {p["path"]: p["updated"] for p in run(shallow)["pages"]}
        # Fetched: "three", "two" and the boundary commit "one", which lists
        # every file as added and is therefore ignored.
        self.assertEqual(
            pages,
            {
                "index.md": "2024-06-02",
                "operations/index.md": "2024-06-02",
                "operations/reconfigure-nova.md": "2024-05-17",
            },
        )

    def test_without_git_history(self) -> None:
        plain = Path(self._tmp.name) / "plain"
        write(plain, "docs/index.md", "# Home\n")
        data = run(plain)
        self.assertEqual(data, {
            "generated": None,
            "pages": [{"path": "index.md", "url": "", "title": "Home", "updated": None}],
        })

    def test_a_move_without_a_change_is_not_an_update(self) -> None:
        # The pages move to docs/ussuri/, as when the portal got releases; one
        # of them is edited in the same commit, another one later.
        git(self.repo, "mv", "docs", "ussuri")
        (self.repo / "docs").mkdir()
        git(self.repo, "mv", "ussuri", "docs/ussuri")
        write(self.repo, "docs/ussuri/operations/index.md", "# Operations\n\nHub, edited while moving.\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "move", date="2024-07-01T08:00:00+00:00")
        write(self.repo, "docs/ussuri/index.md", "---\ntitle: Home\n---\n\n# Home\n\nEdited.\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "edit", date="2024-08-05T08:00:00+00:00")
        assert prebuild.main(["--root", str(self.repo), "--docs-dir", "docs/ussuri", "--skip-vendor"]) == 0
        data = json.loads((self.repo / "docs/ussuri/assets/data/updates.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {page["path"]: page["updated"] for page in data["pages"]},
            {
                "index.md": "2024-08-05",  # edited after the move
                "operations/index.md": "2024-07-01",  # edited by the move
                "operations/reconfigure-nova.md": "2024-05-17",  # only moved
            },
        )

    def test_releases_of_the_registry(self) -> None:
        git(self.repo, "mv", "docs", "ussuri")
        (self.repo / "docs/day2").mkdir(parents=True)
        git(self.repo, "mv", "ussuri", "docs/day2/ussuri")
        write(
            self.repo,
            "academy.toml",
            '[[module]]\nid = "day2"\nstep = "Operate"\ntitle = "Day two"\nsummary = "S."\n'
            'kind = "versioned"\ndefault = "ussuri"\n'
            '[[module.release]]\nid = "ussuri"\nstatus = "available"\nopenstack = "Ussuri"\n'
            'kolla_ansible = "10.x"\ntag = "ussuri-eol"\n'
            '[[module.release]]\nid = "2023.1"\nstatus = "planned"\nopenstack = "2023.1 Antelope"\n'
            'kolla_ansible = "16.x"\n',
        )
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(prebuild.main(["--root", str(self.repo), "--skip-vendor"]), 0)
            # A planned release has no pages to prepare; an unknown one is refused.
            self.assertEqual(prebuild.main(["--root", str(self.repo), "--skip-vendor", "--release", "day2/2023.1"]), 1)
            self.assertEqual(prebuild.main(["--root", str(self.repo), "--skip-vendor", "--release", "nope"]), 1)
        self.assertTrue((self.repo / "docs/day2/ussuri/assets/data/updates.json").is_file())
        self.assertFalse((self.repo / "docs/day2/2023.1").exists())
        self.assertIn("planned", err.getvalue())
        self.assertIn("not a site", err.getvalue())

    def test_front_matter_title_forms(self) -> None:
        title = prebuild.front_matter_title
        self.assertEqual(title("---\ntitle: Plain title\n---\n"), "Plain title")
        self.assertEqual(title('---\ntitle: "Quoted: \\"x\\""\n---\n'), 'Quoted: "x"')
        self.assertEqual(title("---\ntitle: 'It''s'\n---\n"), "It's")
        self.assertEqual(title("---\ndescription: x\n---\n"), None)
        self.assertEqual(title("# No front matter\n"), None)


class VendorStepTest(unittest.TestCase):
    """prebuild.py hands the vendored Mermaid bundle to fetch_vendor.py."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        write(self.root, "docs/index.md", "# Home\n")
        self.fetch_vendor = prebuild.load_fetch_vendor()
        patcher = mock.patch.object(prebuild, "load_fetch_vendor", return_value=self.fetch_vendor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def main(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            status = prebuild.main(["--root", str(self.root), "--docs-dir", "docs", *args])
        return status, err.getvalue()

    def test_missing_bundle_is_fetched(self) -> None:
        with mock.patch.object(self.fetch_vendor, "download") as download, mock.patch.object(
            self.fetch_vendor, "check_tarball"
        ), mock.patch.object(self.fetch_vendor, "extract_member", return_value=b"bundle"), mock.patch.object(
            self.fetch_vendor, "FILE_SHA256", "6b0ea5d9d8ac8a5c6fa7a0a3a4b6ff1ba6ad4eb17a5bfe9a9d3f0e9c9d2f1c11"
        ), mock.patch.object(self.fetch_vendor, "install") as install:
            status, _ = self.main()
        self.assertEqual(status, 0)
        download.assert_called_once()
        install.assert_called_once()
        self.assertEqual(
            install.call_args.args[1], self.root / "overrides/assets/vendor/mermaid/mermaid.min.js"
        )
        self.assertTrue((self.root / "docs/assets/data/updates.json").is_file())

    def test_bundle_in_place_needs_no_network(self) -> None:
        with mock.patch.object(self.fetch_vendor, "is_current", return_value=True), mock.patch.object(
            self.fetch_vendor, "download", side_effect=AssertionError("network used")
        ):
            status, _ = self.main()
        self.assertEqual(status, 0)

    def test_failure_stops_the_prebuild(self) -> None:
        with mock.patch.object(
            self.fetch_vendor, "download", side_effect=self.fetch_vendor.VendorError("download failed: test")
        ):
            status, err = self.main()
        self.assertEqual(status, 1)
        self.assertIn("download failed: test", err)
        self.assertIn("--skip-vendor", err)
        self.assertFalse((self.root / "docs/assets/data/updates.json").exists())

    def test_skip_vendor(self) -> None:
        with mock.patch.object(self.fetch_vendor, "ensure", side_effect=AssertionError("called")):
            status, _ = self.main("--skip-vendor")
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
