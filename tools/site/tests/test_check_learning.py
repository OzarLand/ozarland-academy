"""Unit tests for tools/site/check_learning.py (needs PyYAML, as the build).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_learning", Path(__file__).resolve().parents[1] / "check_learning.py"
)
check_learning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_learning)

TOML = """
[project.extra.journey]
page = "start/learning-journey/"

[[project.extra.journey.stages]]
id = "discover"
pages = []

[[project.extra.journey.stages]]
id = "master"
pages = []
"""

GOOD_PAGE = """---
title: A page
remember:
  - "A tag never restricts which hosts a play targets: use <code>--limit</code>."
  - "Handlers ignore tags <span class=\\"ev ev-code\\">CODE</span>."
  - "Nothing was run against a host."
scenarios:
  - title: "A situation"
    situation: "You need to change one thing."
    choices:
      - text: "Check first"
        verdict: "best"
        why: "The page says so."
      - text: "Run it everywhere"
        verdict: "avoid"
        why: "Every host restarts."
      - text: "Run it at night"
        verdict: "risky"
        why: "Still every host."
    see: "4-practical-consequences"
quiz:
  - q: "Does a tag restrict hosts?"
    options: ["Yes", "No"]
    answer: 1
    explain: "Use <code>--limit</code>."
    see: "4-practical-consequences"
---

# A page
"""

JOURNEY = """---
title: Journey
challenges:
  discover:
    - q: "Q1"
      options: ["a", "b", "c"]
      answer: 2
      explain: "E"
      see: "risk/tags/#4-practical-consequences"
    - q: "Q2"
      options: ["a", "b", "c"]
      answer: 0
      explain: "E"
      see: "risk/tags/"
  master:
    - q: "Q1"
      options: ["a", "b"]
      answer: 1
      explain: "E"
    - q: "Q2"
      options: ["a", "b"]
      answer: 0
      explain: "E"
---

# Journey
"""


class CheckLearningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "zensical.base.toml").write_text(TOML, encoding="utf-8")
        (self.root / "academy.toml").write_text(
            '[[module]]\nid = "r1"\nstep = "S"\ntitle = "R1"\nsummary = "S."\nkind = "single"\nstatus = "available"\n',
            encoding="utf-8",
        )
        self.release = self.root / "docs" / "r1"
        (self.release / "risk").mkdir(parents=True)
        (self.release / "start").mkdir()
        (self.release / "risk" / "tags.md").write_text(GOOD_PAGE, encoding="utf-8")
        (self.release / "start" / "learning-journey.md").write_text(JOURNEY, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_check(self) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            status = check_learning.main(["--root", str(self.root)])
        return status, err.getvalue()

    def write(self, rel: str, text: str) -> None:
        (self.release / rel).write_text(text, encoding="utf-8")

    def test_good_pages_pass(self) -> None:
        self.assertEqual(self.run_check(), (0, ""))

    def test_answer_out_of_range(self) -> None:
        self.write("risk/tags.md", GOOD_PAGE.replace("answer: 1", "answer: 2"))
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("`answer` 2 is not an index", out)

    def test_two_best_choices(self) -> None:
        self.write("risk/tags.md", GOOD_PAGE.replace('verdict: "avoid"', 'verdict: "best"'))
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn('2 "best" choices', out)

    def test_unknown_verdict_and_key(self) -> None:
        text = GOOD_PAGE.replace('verdict: "risky"', 'verdict: "maybe"').replace("    see: \"4-", "    hint: \"x\"\n    see: \"4-", 1)
        self.write("risk/tags.md", text)
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("`verdict` 'maybe'", out)
        self.assertIn("unknown key `hint`", out)

    def test_text_rules(self) -> None:
        text = GOOD_PAGE.replace("Nothing was run against a host.", "Use `--limit` [CODE] <b>now</b>")
        self.write("risk/tags.md", text)
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("backticks", out)
        self.assertIn("[CODE]", out)
        self.assertIn("uses <b>", out)

    def test_remember_size(self) -> None:
        text = GOOD_PAGE.replace('  - "Nothing was run against a host."\n', "")
        text = text.replace('  - "Handlers ignore tags <span class=\\"ev ev-code\\">CODE</span>."\n', "")
        self.write("risk/tags.md", text)
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("`remember` is not a list of 3 to 5", out)

    def test_quiz_see_must_be_an_anchor(self) -> None:
        self.write("risk/tags.md", GOOD_PAGE.replace('see: "4-practical-consequences"\n---', 'see: "#4-practical"\n---'))
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("is not an anchor of the page", out)

    def test_challenge_rules(self) -> None:
        text = JOURNEY.replace('see: "risk/tags/"', 'see: "risk/missing/"').replace("  master:", "  extra:")
        self.write("start/learning-journey.md", text)
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("no page risk/missing.md", out)
        self.assertIn("`extra`, not a stage id", out)
        self.assertIn("no challenge for the stage `master`", out)

    def test_challenges_only_on_the_journey_page(self) -> None:
        self.write("risk/tags.md", GOOD_PAGE.replace("title: A page\n", "title: A page\nchallenges: {}\n"))
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("belongs only on start/learning-journey.md", out)

    def test_invalid_yaml(self) -> None:
        self.write("risk/tags.md", GOOD_PAGE.replace('options: ["Yes", "No"]', 'options: ["Yes", "No"'))
        status, out = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn("not valid YAML", out)


if __name__ == "__main__":
    unittest.main()
