"""Unit tests for tools/site/redirect_site.py (standard library only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
SPEC = importlib.util.spec_from_file_location("redirect_site", HERE / "redirect_site.py")
redirect_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(redirect_site)

from test_releases import make_repo, write  # noqa: E402

PORTAL = "https://academy.example.org/"


class RedirectSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        make_repo(self.root)
        self.out = Path(tmp.name) / "out"

    def build(self, *extra: str) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = redirect_site.main([str(self.out), "--to", PORTAL, "--root", str(self.root), *extra])
        self.assertEqual(status, 0)
        return out.getvalue()

    def target(self, rel: str) -> str:
        text = (self.out / rel / "index.html").read_text(encoding="utf-8")
        return re.search(r'<link rel="canonical" href="([^"]+)">', text).group(1)

    def test_every_page_of_every_release_redirects_to_day2(self) -> None:
        self.build()
        self.assertEqual(self.target(""), f"{PORTAL}day2/")
        self.assertEqual(self.target("ussuri"), f"{PORTAL}day2/ussuri/")
        self.assertEqual(self.target("ussuri/operations/reconfigure-nova"), f"{PORTAL}day2/ussuri/operations/reconfigure-nova/")
        # A planned release has its home only.
        self.assertEqual(self.target("2023.1"), f"{PORTAL}day2/2023.1/")

    def test_addresses_without_a_release_lead_to_ussuri(self) -> None:
        self.build()
        self.assertEqual(self.target("operations/reconfigure-nova"), f"{PORTAL}day2/ussuri/operations/reconfigure-nova/")
        self.assertFalse((self.out / "assets").exists())

    def test_page_keeps_query_and_fragment_and_is_not_indexed(self) -> None:
        self.build()
        text = (self.out / "ussuri/index.html").read_text(encoding="utf-8")
        self.assertIn('<meta http-equiv="refresh" content="0; url=https://academy.example.org/day2/ussuri/">', text)
        self.assertIn('location.replace("https://academy.example.org/day2/ussuri/" + location.search + location.hash)', text)
        self.assertIn('<meta name="robots" content="noindex">', text)

    def test_not_found_page_knows_the_rules(self) -> None:
        self.build()
        text = (self.out / "404.html").read_text(encoding="utf-8")
        data = json.loads(re.search(r"var data = (\{.*?\});", text).group(1))
        self.assertEqual(data["former"], "/kolla-ansible-academy/")
        self.assertEqual(data["portal"], PORTAL)
        self.assertEqual(data["unprefixed"], "ussuri")
        self.assertEqual(data["releases"], ["2023.1", "ussuri"])
        self.assertTrue((self.out / ".nojekyll").is_file())

    def test_output_is_replaced_and_address_must_be_https(self) -> None:
        write(self.out, "stale.html", "old")
        self.build()
        self.assertFalse((self.out / "stale.html").exists())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            redirect_site.main([str(self.out), "--to", "http://academy.example.org/", "--root", str(self.root)])


if __name__ == "__main__":
    unittest.main()
