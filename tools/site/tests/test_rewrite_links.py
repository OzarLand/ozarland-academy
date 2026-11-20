"""Unit tests for tools/site/rewrite_links.py (standard library only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("rewrite_links", HERE / "rewrite_links.py")
rewrite_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rewrite_links)

REGISTRY = """
[[module]]
id = "lab"
step = "Discover"
title = "Quick lab"
summary = "Lab."
kind = "single"
status = "available"

[[module]]
id = "day2"
step = "Operate"
title = "Day 2"
summary = "Day 2."
kind = "versioned"
default = "ussuri"

[[module.release]]
id = "ussuri"
status = "available"
openstack = "Ussuri"
kolla_ansible = "10.x"
tag = "ussuri-eol"

[[module]]
id = "runbooks"
step = "Intervene"
title = "VM runbooks"
summary = "Runbooks."
kind = "single"
status = "available"

[[module]]
id = "production"
step = "Go to production"
title = "Production guide"
summary = "Production."
kind = "single"
status = "planned"
"""

LAB = "https://github.com/OzarLand/openstack-quick-lab"
RUNBOOKS = "https://github.com/OzarLand/openstack-vm-runbooks"


class RewriteTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        files = {
            "academy.toml": REGISTRY,
            "docs/lab/index.md": "# Lab\n",
            "docs/lab/exercises/index.md": "# Exercises\n",
            "docs/lab/exercises/01-dhcp.md": "# DHCP\n",
            "docs/lab/variants/cloud/index.md": "# Cloud\n",
            "docs/lab/variants/cloud/create.sh": "#!/bin/sh\n",
            "docs/runbooks/index.md": "# Runbooks\n",
            "docs/runbooks/networking/no-ip.md": "# No IP\n",
            "docs/runbooks/scripts/check.sh": "#!/bin/sh\n",
        }
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.rewriter = rewrite_links.Rewriter(self.root)

    def rewrite(self, source: str, text: str) -> str:
        return self.rewriter.rewrite(source, text)

    def test_relative_readme_becomes_index(self) -> None:
        out = self.rewrite("docs/lab/variants/cloud/index.md", "[home](../../README.md#pick) and [ex](../../exercises/README.md)")
        self.assertEqual(out, "[home](../../index.md#pick) and [ex](../../exercises/index.md)")

    def test_dropped_files(self) -> None:
        out = self.rewrite("docs/lab/index.md", '[Apache-2.0](LICENSE), <a href="CODE_OF_CONDUCT.md#reporting">x</a>')
        self.assertIn(f"({rewrite_links.REPOSITORY}/blob/main/LICENSE)", out)
        self.assertIn(f'href="{rewrite_links.HUB}/blob/main/CODE_OF_CONDUCT.md#reporting"', out)

    def test_absolute_link_to_a_page_of_the_same_module(self) -> None:
        out = self.rewrite("docs/lab/exercises/01-dhcp.md", f"[x]({LAB}/blob/main/variants/cloud/README.md#quick)")
        self.assertEqual(out, "[x](../variants/cloud/index.md#quick)")

    def test_absolute_link_to_a_page_of_another_module(self) -> None:
        out = self.rewrite("docs/lab/exercises/01-dhcp.md", f"[r]({RUNBOOKS}/blob/main/networking/no-ip.md#check)")
        self.assertEqual(out, "[r](../../runbooks/networking/no-ip/#check)")

    def test_repository_root_and_directory(self) -> None:
        out = self.rewrite("docs/lab/index.md", f"[r]({RUNBOOKS}) [t]({RUNBOOKS}/tree/main/networking)")
        self.assertEqual(out, f"[r](../runbooks/) [t]({rewrite_links.REPOSITORY}/tree/main/docs/runbooks/networking)")

    def test_script_goes_to_this_repository(self) -> None:
        out = self.rewrite("docs/lab/index.md", f"[s]({RUNBOOKS}/blob/main/scripts/check.sh)")
        self.assertEqual(out, f"[s]({rewrite_links.REPOSITORY}/blob/main/docs/runbooks/scripts/check.sh)")

    def test_planned_module_issues_and_code_stay(self) -> None:
        text = (
            "[p](https://github.com/OzarLand/production-guide/blob/main/memo.md) "
            f"[i]({LAB}/issues/25) `{RUNBOOKS}/blob/main/networking/no-ip.md`\n"
            f"```bash\ngit clone {RUNBOOKS}\n```"
        )
        self.assertEqual(self.rewrite("docs/lab/index.md", text), text)

    def test_missing_file_is_reported(self) -> None:
        text = f"[gone]({RUNBOOKS}/blob/main/networking/gone.md)"
        self.assertEqual(self.rewrite("docs/lab/index.md", text), text)
        self.assertEqual(len(self.rewriter.unmapped), 1)

    def test_apply_is_idempotent(self) -> None:
        page = self.root / "docs/lab/exercises/01-dhcp.md"
        page.write_text(f"# DHCP\n\n[r]({RUNBOOKS}/blob/main/networking/no-ip.md) [h](../README.md)\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rewrite_links.main(["--apply", "--root", str(self.root)])
            first = page.read_text(encoding="utf-8")
            rewrite_links.main(["--apply", "--root", str(self.root)])
        self.assertEqual(page.read_text(encoding="utf-8"), first)
        self.assertIn("[r](../../runbooks/networking/no-ip/) [h](../index.md)", first)


if __name__ == "__main__":
    unittest.main()
