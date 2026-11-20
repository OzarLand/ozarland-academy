#!/usr/bin/env python3
"""Check the learning blocks of the front matter of every page.

The pages of a release can carry four learning blocks in their front matter,
rendered by overrides/main.html and overrides/journey.html:

    remember     3 to 5 short takeaways (strings)
    scenarios    "What would you do?": situations with three choices, exactly
                 one of them "best", the others "risky" or "avoid"
    quiz         "Check yourself": questions with options and the index of
                 the right one
    challenges   the final challenge of each stage of the learning journey
                 (only on start/learning-journey.md), keyed by the stage ids
                 of [project.extra.journey] in zensical.base.toml

A malformed block would break the template or, worse, show a wrong answer as
right, so this script checks their shape and their text:

* the expected keys and types, no unknown key;
* `answer` is an index of `options`; exactly one "best" choice;
* the text uses inline HTML only from a short list (<code>, <strong>, <em>,
  <span class="ev ev-code"> and <span class="ev ev-na">), never Markdown
  backticks nor the bracketed evidence labels "[CODE]" / "[NOT AVAILABLE]",
  which the templates do not render;
* `see` is an anchor of the page (quiz, scenarios: check_site checks that it
  exists) or, in a challenge, the path of a page of the release, with an
  optional anchor, whose Markdown source exists.

    python3 tools/site/check_learning.py [--strict] [--release PATH]

Exit status 1 when an error is found. Needs PyYAML, a pinned dependency of
the build (requirements-docs.txt).
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

import yaml

# The registry of the portal (academy.toml) is read by releases.py, next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
JOURNEY_PAGE = "start/learning-journey.md"
VERDICTS = ("best", "risky", "avoid")
REMEMBER_MIN, REMEMBER_MAX = 3, 5
CHOICES = 3

_TAG = re.compile(r"<(/?)([a-zA-Z]+)([^>]*)>")
_ALLOWED_TAGS = {"code", "strong", "em", "span"}
_SPAN_CLASSES = {'class="ev ev-code"', 'class="ev ev-na"'}
_ANCHOR = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PAGE_PATH = re.compile(r"^[a-z0-9][a-z0-9./_-]*/(#[a-z0-9][a-z0-9_-]*)?$")


def front_matter(text: str) -> tuple[dict, int] | None:
    """The front matter of a page as data, and the line where its body starts."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    data = yaml.safe_load(text[4:end]) or {}
    return (data if isinstance(data, dict) else {}), text.count("\n", 0, end) + 2


def key_line(text: str, key: str) -> int:
    """Line of `key:` at the start of a line of the front matter, else 1."""
    match = re.search(rf"^{re.escape(key)}:", text, re.MULTILINE)
    return text.count("\n", 0, match.start()) + 1 if match else 1


class Checker:
    def __init__(self, stage_ids: list[str]) -> None:
        self.stage_ids = stage_ids
        self.errors: list[str] = []
        self.counts = {"remember": 0, "scenarios": 0, "quiz": 0, "challenges": 0}

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    # --- text ---------------------------------------------------------------
    def text(self, where: str, value: object, field: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            self.error(where, f"`{field}` is missing or not a text")
            return False
        if "`" in value:
            self.error(where, f"`{field}` uses Markdown backticks: write <code>…</code>")
        for label in ("[CODE]", "[NOT AVAILABLE]"):
            if label in value:
                self.error(where, f"`{field}` writes {label}: use the <span class=\"ev …\"> chip")
        stack: list[str] = []
        for closing, tag, attrs in _TAG.findall(value):
            tag = tag.lower()
            if tag not in _ALLOWED_TAGS:
                self.error(where, f"`{field}` uses <{tag}>, not one of {sorted(_ALLOWED_TAGS)}")
                continue
            if closing:
                if not stack or stack.pop() != tag:
                    self.error(where, f"`{field}` closes </{tag}> without opening it")
            else:
                if tag == "span" and attrs.strip() not in _SPAN_CLASSES:
                    self.error(where, f"`{field}` has a <span> other than the evidence chips")
                elif tag != "span" and attrs.strip():
                    self.error(where, f"`{field}` gives attributes to <{tag}>")
                stack.append(tag)
        if stack:
            self.error(where, f"`{field}` leaves <{stack[-1]}> open")
        return True

    @staticmethod
    def unknown(item: dict, allowed: set[str]) -> list[str]:
        return sorted(set(item) - allowed)

    # --- blocks -------------------------------------------------------------
    def remember(self, where: str, value: object) -> None:
        if not isinstance(value, list) or not REMEMBER_MIN <= len(value) <= REMEMBER_MAX:
            self.error(where, f"`remember` is not a list of {REMEMBER_MIN} to {REMEMBER_MAX} texts")
            return
        self.counts["remember"] += 1
        for number, item in enumerate(value, 1):
            self.text(f"{where} item {number}", item, "remember")

    def questions(self, where: str, value: object, block: str, see_path: bool) -> None:
        if not isinstance(value, list) or not value:
            self.error(where, f"`{block}` is not a non-empty list of questions")
            return
        for number, item in enumerate(value, 1):
            here = f"{where} question {number}"
            if not isinstance(item, dict):
                self.error(here, "is not a mapping")
                continue
            for key in self.unknown(item, {"q", "options", "answer", "explain", "see"}):
                self.error(here, f"unknown key `{key}`")
            self.text(here, item.get("q"), "q")
            self.text(here, item.get("explain"), "explain")
            options = item.get("options")
            if not isinstance(options, list) or len(options) < 2:
                self.error(here, "`options` is not a list of at least 2 texts")
                options = []
            for option in options:
                self.text(here, option, "options")
            answer = item.get("answer")
            if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
                self.error(here, f"`answer` {answer!r} is not an index of `options` (0 to {len(options) - 1})")
            self.see(here, item.get("see"), see_path)

    def see(self, where: str, see: object, as_path: bool) -> None:
        if see is None:
            return
        if not isinstance(see, str):
            self.error(where, "`see` is not a text")
        elif as_path:
            if not _PAGE_PATH.match(see):
                self.error(where, f"`see` {see!r} is not a page path such as `risk/tags/#anchor`")
            elif self.release_dir is not None:
                page = see.split("#", 1)[0].rstrip("/")
                if not ((self.release_dir / f"{page}.md").is_file()
                        or (self.release_dir / page / "index.md").is_file()):
                    self.error(where, f"`see` {see!r}: no page {page}.md in the release")
        elif not _ANCHOR.match(see):
            self.error(where, f"`see` {see!r} is not an anchor of the page (no `#`, no path)")

    def scenarios(self, where: str, value: object) -> None:
        if not isinstance(value, list) or not value:
            self.error(where, "`scenarios` is not a non-empty list")
            return
        self.counts["scenarios"] += 1
        for number, item in enumerate(value, 1):
            here = f"{where} scenario {number}"
            if not isinstance(item, dict):
                self.error(here, "is not a mapping")
                continue
            for key in self.unknown(item, {"title", "situation", "ask", "choices", "see"}):
                self.error(here, f"unknown key `{key}`")
            self.text(here, item.get("title"), "title")
            self.text(here, item.get("situation"), "situation")
            if "ask" in item:
                self.text(here, item.get("ask"), "ask")
            self.see(here, item.get("see"), as_path=False)
            choices = item.get("choices")
            if not isinstance(choices, list) or len(choices) != CHOICES:
                self.error(here, f"`choices` is not a list of {CHOICES} choices")
                continue
            verdicts = []
            for index, choice in enumerate(choices, 1):
                at = f"{here} choice {index}"
                if not isinstance(choice, dict):
                    self.error(at, "is not a mapping")
                    continue
                for key in self.unknown(choice, {"text", "verdict", "why"}):
                    self.error(at, f"unknown key `{key}`")
                self.text(at, choice.get("text"), "text")
                self.text(at, choice.get("why"), "why")
                verdict = choice.get("verdict")
                if verdict not in VERDICTS:
                    self.error(at, f"`verdict` {verdict!r} is not one of {', '.join(VERDICTS)}")
                verdicts.append(verdict)
            if verdicts.count("best") != 1:
                self.error(here, f"has {verdicts.count('best')} \"best\" choices instead of exactly 1")

    def challenges(self, where: str, value: object) -> None:
        if not isinstance(value, dict):
            self.error(where, "`challenges` is not a mapping of stage ids")
            return
        self.counts["challenges"] += 1
        for stage in value:
            if stage not in self.stage_ids:
                self.error(where, f"`challenges` has `{stage}`, not a stage id ({', '.join(self.stage_ids)})")
        for stage in self.stage_ids:
            if stage not in value:
                self.error(where, f"`challenges` has no challenge for the stage `{stage}`")
            else:
                questions = value[stage]
                if isinstance(questions, list) and len(questions) < 2:
                    self.error(where, f"the challenge of `{stage}` has fewer than 2 questions")
                self.questions(f"{where} challenge {stage}", questions, "challenges", see_path=True)

    # --- pages --------------------------------------------------------------
    release_dir: Path | None = None

    def page(self, path: Path, rel: str, release_dir: Path) -> None:
        text = path.read_text(encoding="utf-8")
        try:
            parsed = front_matter(text)
        except yaml.YAMLError as exc:
            self.error(rel, f"front matter is not valid YAML: {exc}".splitlines()[0])
            return
        if parsed is None:
            return
        front, _ = parsed
        self.release_dir = release_dir
        page = path.relative_to(release_dir).as_posix()
        if "remember" in front:
            self.remember(f"{rel}:{key_line(text, 'remember')}", front["remember"])
        if "scenarios" in front:
            self.scenarios(f"{rel}:{key_line(text, 'scenarios')}", front["scenarios"])
        if "quiz" in front:
            self.counts["quiz"] += 1
            self.questions(f"{rel}:{key_line(text, 'quiz')}", front["quiz"], "quiz", see_path=False)
        if "challenges" in front:
            where = f"{rel}:{key_line(text, 'challenges')}"
            if page != JOURNEY_PAGE:
                self.error(where, f"`challenges` belongs only on {JOURNEY_PAGE}")
            else:
                self.challenges(where, front["challenges"])


def stage_ids(root: Path) -> list[str]:
    config = tomllib.loads((root / "zensical.base.toml").read_text(encoding="utf-8"))
    stages = config.get("project", {}).get("extra", {}).get("journey", {}).get("stages", [])
    return [stage["id"] for stage in stages]


def release_dirs(root: Path, release: str | None) -> list[Path]:
    """Docs directories of the available sites of academy.toml, or of the one named."""
    registry = releases.load_registry(root)
    return [root / site.docs_dir for site in releases.select(registry, release) if (root / site.docs_dir).is_dir()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="accepted for symmetry: every finding is an error")
    parser.add_argument("--release", metavar="PATH", help="check only this site, such as day2/2023.1")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    checker = Checker(stage_ids(args.root))
    try:
        dirs = release_dirs(args.root, args.release)
    except releases.RegistryError as error:
        for problem in error.problems:
            print(f"check_learning: {releases.REGISTRY_FILE}: {problem}", file=sys.stderr)
        return 1
    for release_dir in dirs:
        for path in sorted(release_dir.rglob("*.md")):
            checker.page(path, path.relative_to(args.root).as_posix(), release_dir)
    for line in checker.errors:
        print(line, file=sys.stderr)
    counts = ", ".join(f"{count} with {block}" for block, count in checker.counts.items())
    status = "OK" if not checker.errors else f"{len(checker.errors)} error(s)"
    print(f"check_learning: {status} - pages: {counts}")
    return 1 if checker.errors else 0


if __name__ == "__main__":
    sys.exit(main())
