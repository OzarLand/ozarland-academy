# Contributing

> **Looking for the quick way?** To confirm that a page worked on your platform, fix an error or propose a page:
>
> - VM runbooks: [docs/runbooks/CONTRIBUTING.md](docs/runbooks/CONTRIBUTING.md) (three ways to help, from the smallest)
> - Deployment patterns: [docs/deploy/CONTRIBUTING.md](docs/deploy/CONTRIBUTING.md)
> - Quick lab: [docs/lab/CONTRIBUTING.md](docs/lab/CONTRIBUTING.md)
> - Production guide: [docs/production/CONTRIBUTING.md](docs/production/CONTRIBUTING.md)
> - Operator skills: [docs/skills/CONTRIBUTING.md](docs/skills/CONTRIBUTING.md)
>
> The rest of this page is for the day-2 module, Kolla-Ansible Academy, and for the tooling of the portal.

OzarLand Academy is one learning path made of modules, listed in [academy.toml](academy.toml). The portal is generated
from the Markdown under `docs/`: one directory and one site per module (`docs/<module>/`), and for the day-2 module,
Kolla-Ansible Academy, one per release (`docs/day2/<release>/`). A change to the content is a change to those files;
nothing exists only in a template, a script or a stylesheet.

Most of this page is about the day-2 module: how to add or change one of its pages, and how to add a release. Three
releases are available today; the paths below are those of `ussuri`, and another release has the same layout under
its own directory. The other modules have their own rules, in the pages of the module
([Quick lab](docs/lab/CONTRIBUTING.md), [Deployment patterns](docs/deploy/CONTRIBUTING.md),
[VM runbooks](docs/runbooks/CONTRIBUTING.md), [Production guide](docs/production/CONTRIBUTING.md)); Deployment
patterns and VM runbooks also follow the content conventions of the OzarLand hub, checked by `make docs-content`, and
the pages of the Production guide are generated from its memo sources by its own build (`docs/production/`, Node); every module follows the rules on links below and the
checks of [Before a pull request](#before-a-pull-request). How a former repository becomes a module is at the end:
[Moving a repository into a module](#moving-a-repository-into-a-module).

A link to a page of another module or of another release is not a link to its `.md` file: each site is built on its
own. Write the address of the page relative to the file, ending with `/`, for example
`[Conventions of 2023.1](../../2023.1/start/conventions/)` from `docs/day2/2024.1/start/`. Never write the address of
the portal in full: the pages must work at any address. `check_docs.py` checks both (rules `link-site` and
`link-site-address`).

## The evidence rule

Each release is a source-code study of one Kolla-Ansible tag: `ussuri-eol` for `docs/day2/ussuri/`. Every statement is one
of two things:

- **[CODE]**: shown by the sources, with a `path:line` citation nearby;
- **[NOT AVAILABLE]**: the sources do not establish it.

Nothing else is accepted: no observation from a run, no timing, no statement about another release. A page of
`docs/day2/<release>/` cites the sources of the tag of that release only. The definition of
the two labels, with the path prefixes used in citations, is in [Evidence
labels](docs/day2/ussuri/start/conventions.md#evidence-labels). Introductions, hub pages and descriptions only restate what a
section says, and link to it.

On the site, `[CODE]` and `[NOT AVAILABLE]` show as chips. A label that opens a longer bracket, such as `[CODE: no
ansible.cfg in the tree]` (also `;`, `,` or a space after the label), shows as the chip followed by its note in
parentheses. A code span that is a `path:line` citation (`site.yml:88-103`, `:140-203`) is shown more quietly than a
command, so write citations as their own code spans, without other words inside the backticks.

## Where a page goes

| Directory | Tab | What belongs there |
|---|---|---|
| `docs/day2/ussuri/start/` | Home | Entry pages: lookup by question, the short list to read first, the conventions |
| `docs/day2/ussuri/operations/` | Operations | One page per Day-2 operation: its commands, then what they do, the risks and the verification |
| `docs/day2/ussuri/troubleshooting/` | Troubleshooting | The symptom index, known bugs and limitations, open questions, what is not known |
| `docs/day2/ussuri/components/` | Components | One page per component, ending with its generated service card; pages that cut across components |
| `docs/day2/ussuri/risk/` | Risk and impact | The risk register, what a tag really executes, the tag index |
| `docs/day2/ussuri/concepts/` | Concepts | How Kolla-Ansible is built and how a run works |
| `docs/day2/ussuri/reference/` | Reference | Findings, glossary, generated inventory, fact sheets, Ansible listings, method and limits |

A new page is then listed in two places:

1. the hub of its tab (`index.md` of the directory): each hub lists every page of its tab, and the
   [Operations catalogue](docs/day2/ussuri/operations/index.md#operations-catalogue) has one row per operation page;
2. the `nav` list of the release, in [docs/day2/ussuri.toml](docs/day2/ussuri.toml), under its tab. Only the path is written
   there, relative to `docs/day2/ussuri/`: the title comes from the front matter of the page.

## Page skeleton

An operation page, as an example. The other pages have the same parts, without `impact` and without the numbered
command section.

````markdown
---
title: Rotate the example setting
description: One sentence, at most 160 characters, that restates what the page answers.
tags: [nova, reconfigure, loop-notify]
impact: [restarts-on-drift]
---

# Rotate the example setting

One to three sentences: what the page answers, and for which command.

> [!NOTE]
> **Key answers**
>
> - **Short label:** the answer, with its evidence label ([§2](#2-what-restarts)).

## 1. Commands

### 1.1 Name of the command

```bash
kolla-ansible -i multinode -t nova reconfigure
```

- **Scope:** plays and hosts touched.
- **Restarts:** containers that can restart.

## 2. What restarts

[CODE] The statement, with its citation (`roles/nova/tasks/config.yml:10-20`).

## Related

- [Reconfigure Nova](reconfigure-nova.md) — why the reader would go there
````

- `title` has no numbering. `description` is required and has at most 160 characters.
- `tags` are lowercase names of the components and mechanisms the page really covers. Reuse the tags of the existing
  pages (they are the "Tags" filter of the search dialog) before adding a new one.
- `impact` is for operation pages only and uses the classes of [Operation impact
  classes](docs/day2/ussuri/start/conventions.md#operation-impact-classes). A class is used only where the corpus supports it; a
  new use is backed by a section, cited in that table.
- The command sections follow the [conventions used by the command
  sections](docs/day2/ussuri/operations/index.md#conventions-used-by-the-command-sections).
- How pages are built is summarised in [How pages are built](docs/day2/ussuri/start/conventions.md#how-pages-are-built).

## Writing rules

- English, plain and short sentences. Prose is wrapped at 120 columns; table rows are not wrapped.
- **Links** between pages are relative and end in `.md`, with a `#anchor` when they point to a section. They stay
  inside the directory of the release (`docs/day2/ussuri/`) and point to a file, not to a directory or to the published
  URL.
- **A link to a page of another release** is the one exception: each release is a separate site, so the link is the
  absolute address of the published page, for example
  `https://ozarland.github.io/kolla-ansible-academy/ussuri/operations/reconfigure-nova/#2-what-restarts`. A relative
  link such as `../../ussuri/operations/reconfigure-nova.md` is refused: it works on github.com but not on the site.
  `make docs-check` verifies that the release exists and has that page and that anchor. Such a link only points the
  reader to the other study; it is not evidence for the release being written.
- **Anchors** are those of github.com: the heading in lowercase, every character that is not a letter, a digit, an
  underscore, a hyphen or a space dropped, each space replaced by a hyphen; a repeated heading gets `-1`, `-2`. The
  site is configured to produce the same anchors. Other pages link to the existing headings: renaming a heading breaks
  those links, and `make docs-check` reports them.
- **Callouts** are GitHub alerts only: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`, with
  the marker alone on the first line of the blockquote.
- **Fenced code** always has a language: `bash`, `yaml`, `jinja`, `python`, `text` or `mermaid`.
- **Diagrams** are `mermaid` code blocks. The Mermaid bundle is vendored: it is not committed, `make docs-deps`
  downloads the pinned version and verifies its checksum, and the site loads it only on pages that contain a diagram.
  Version, checksums and the update procedure are in
  [overrides/assets/vendor/mermaid/README.md](overrides/assets/vendor/mermaid/README.md).
  A diagram is written in the page of each release, even when two releases draw the same thing (5 of the 34 diagrams
  today): it is evidence of that release's code, so it is not shared with another release, whose code may change.

## Risks, findings and open questions

The items of the [Risk register](docs/day2/ussuri/risk/risk-register.md) (R), of the [Technical
findings](docs/day2/ussuri/reference/findings.md) (F) and of the [Open questions](docs/day2/ussuri/troubleshooting/open-questions.md) (Q) are
sections with an explicit anchor, so that a link such as `../risk/risk-register.md#r12` keeps working when the title of
the item changes. To add an item:

1. Take the next free number. Links target the existing anchors, so the existing items keep their number.
2. Add the section after the last item, in the form of the existing ones: the anchor, a blank line, the heading, then a
   two-column table with the same rows as the other items of the page.

   ```markdown
   <a id="r26"></a>

   ### R26 — Short title

   | | |
   |---|---|
   | **Operation / trigger** | … |
   ```

3. Add its row to the summary table of the page ("Matrix", "Headline findings" or "Summary").
4. Cite it from other pages by its number, linked to its anchor: `[R26](../risk/risk-register.md#r26)`.
5. Search `docs/day2/ussuri/` for the sentences that give the number of items ("25 risks", "R1–R25", "fifteen headline findings",
   "Q1–Q14") and update them.

## Generated content

Two parts of each release are written by the generators of `tools/` and must not be edited by hand:

- the service card of each component page, between `<!-- BEGIN GENERATED: tools/service_cards.py <role> -->` and
  `<!-- END GENERATED -->`;
- [docs/day2/ussuri/reference/generated-inventory.md](docs/day2/ussuri/reference/generated-inventory.md), except its front
  matter.

To regenerate them, use a checkout of `openstack/kolla-ansible` at the tag of the release (`ussuri-eol` for `ussuri`;
the tag is in `academy.toml`). Both scripts need PyYAML; the first one also needs the example `multinode` inventory
as JSON. `--release` names the release to write into; without it, it is the default release of the day-2 module:

```bash
ansible-inventory -i <checkout>/ansible/inventory/multinode --list > inventory.json
python3 tools/service_cards.py --release ussuri <checkout> inventory.json   # the cards under docs/day2/ussuri/components/
python3 tools/extract_kolla_inventory.py --release ussuri <checkout>        # docs/day2/ussuri/reference/generated-inventory.md
```

The scripts were written for the Ussuri tree. For another release, read their output against the sources of that
release before trusting it: a role or a file layout that changed upstream may need a change in the generator.

`service_cards.py` rewrites only the text between the markers. `extract_kolla_inventory.py` keeps the front matter of
the output file and rewrites its body. A change to a card or to the inventory is a change to the generator.

## Adding a release

A new release is a **new study**, made from the sources of that release. The pages of Ussuri must not be copied and
assumed valid: a task, a default, a handler or a tag may differ, and nothing in the copy would say so. Every statement
of the new release needs its own evidence, a `path:line` citation in the code of the tag that is studied, or the label
[NOT AVAILABLE]. A page may reuse the structure of an Ussuri page, never its statements.

The releases are listed in [academy.toml](academy.toml), one `[[module.release]]` block each, under the block of the
module `day2`. A release is either `planned` or `available`.

### A planned release

A planned release has no directory and no content. To add one, add its block to `academy.toml`; to remove one,
remove the block. Nothing else changes.

```toml
[[module.release]]
id = "victoria"
status = "planned"
openstack = "Victoria"
kolla_ansible = "11.x"
```

The portal then lists it in the release selector under "Coming soon" and publishes one generated page at
`/day2/victoria/`, which says that the study is not available yet and links to the available releases. Any other
address under `/day2/victoria/` leads to that page. The text of the page is in `overrides/planned.html`, the same for every planned
release.

### Making a release available

The steps are the same for a release that is already planned and for one that is not in the registry yet. `<id>` is
the id of the release: lowercase letters, digits, dots and hyphens (`victoria`, `2023.1`). It is the name of the
directory, the URL segment and the key of the registry.

1. **Create the content** in `docs/day2/<id>/`, with the layout of [Where a page goes](#where-a-page-goes). The minimum is
   a home page, `docs/day2/<id>/index.md`, whose front matter has `template: home.html`, a `title` and a `description`.
   Write the pages from the sources of the tag that is studied (see above). Two things in the shared templates
   expect a page of the release: an operation page that sets `impact` gets chips that link to
   `start/conventions.md#operation-impact-classes`, so the release needs that page and that heading before its first
   `impact`; and the class names are fixed by `check_docs.py` (rule `impact`), the same for every release.
2. **Create `docs/day2/<id>.toml`**, next to the directory, with the settings of the release: its description and its
   navigation. Start from [docs/day2/ussuri.toml](docs/day2/ussuri.toml) and keep only the pages that exist:

   ```toml
   [project]
   site_description = "Source-code study of Kolla-Ansible <tag> for Day-2 operations."

   nav = [
     { "Home" = [
       "index.md",
     ] },
   ]
   ```

   Everything else comes from [zensical.base.toml](zensical.base.toml), shared by all sites. The tooling sets
   `docs_dir`, `site_dir`, `site_url` (`<portal address>day2/<id>/`) and `edit_uri` (`blob/main/docs/day2/<id>/`).
3. **Register the release** in `academy.toml`: set `status = "available"` in its block, or add the block, and give
   the upstream tag that is studied.

   ```toml
   [[module.release]]
   id = "victoria"
   status = "available"
   openstack = "Victoria"
   kolla_ansible = "11.x"
   tag = "<upstream tag that is studied>"
   ```

   The order of the blocks is the order of the release selector. Leave `default` of the module as it is: it is the
   release the home of the module (`/day2/`) leads to, and changing it is a separate decision.
4. **Add the release to the table** of [README.md](README.md#operate-kolla-ansible-academy-day2), which lists the
   available releases. A unit test compares the table with `academy.toml`.
5. **Check and build.** `RELEASE=day2/<id>` limits the checks and the build to the new release while it is being
   written:

   ```bash
   make docs-check RELEASE=day2/<id>
   make docs-build RELEASE=day2/<id>
   make docs-serve RELEASE=day2/<id>      # live preview of that release
   make docs-check STRICT=1          # before the pull request: every release
   make docs-build STRICT=1
   make docs-preview                 # the built portal, to try the release selector
   ```

Nothing is copied per release: the templates, the stylesheet, the scripts, the logo and the vendored Mermaid are in
`overrides/` and are shared. The workflow needs no change: it builds every available site of `academy.toml`.

What the checks enforce for a release:

- `academy.toml` and the tree agree: an available release has `docs/day2/<id>/` and `docs/day2/<id>.toml`, a planned
  release has neither, and nothing else sits directly under `docs/day2/` (rule `registry`). An available release without `tag`, an
  id that is not a valid directory name, or a `default` that is not available, is an error.
- Every page of `docs/day2/<id>/` follows the rules of this file (front matter, links, anchors, callouts, code languages)
  and is listed once in the `nav` of `docs/day2/<id>.toml`.
- A link never leaves the release, except as the relative address of a page of another site that exists (rule
  `link-site`).
- In the built portal: every page of the release is built under `/day2/<id>/`, its search index and its sitemap only
  list pages of that release, `day2/versions.json`, the home of the module and the not-found page match
  `academy.toml`, and a planned release has its "coming soon" page and no other.

The checks cannot tell whether a statement was verified in the sources of the new release. That is the review of the
pull request: it reads the citations against the tag named in `academy.toml`.

### Removing a release, changing the default

- To take a release offline, set its status back to `planned` and remove `docs/day2/<id>/`, `docs/day2/<id>.toml` and its row
  in the table of `README.md`, or remove its block as well. Its published pages then lead to the "coming soon" page, or to the not-found page of the portal.
- `default` of the module may be changed to any available release. The home of the module then opens that release.

## Before a pull request

```bash
python3 -m venv .venv     # once
make docs-deps            # once, and after a change of requirements-docs.txt
make docs-check           # the Markdown sources of every site: front matter, links, anchors, callouts, nav
make docs-build           # unit tests, strict build into site/, checks on the built portal
make docs-serve           # live preview of one site, to read the page as the site shows it
```

`make docs-check STRICT=1` and `make docs-build STRICT=1` report the warnings as errors (for example a missing
`description`). The rules of both checks are listed in [tools/site/README.md](tools/site/README.md).

The workflow [.github/workflows/docs.yml](.github/workflows/docs.yml) runs on every pull request that changes `docs/`,
`overrides/`, `tools/site/`, `academy.toml`, `zensical.base.toml`, `requirements-docs.txt`, `Makefile`, `README.md`,
`CONTRIBUTING.md` or the workflow itself. It runs `make docs-deps`, `make docs-check STRICT=1` and `make docs-build STRICT=1`. A pull
request is never deployed: its built portal is uploaded as the artifact `site`, kept 7 days. On `main`, the same build is
followed by the deployment to GitHub Pages.

## Learning journey and levels

The beginner path of each release ("Your learning journey", `docs/day2/<id>/start/learning-journey.md`) is defined once, in
`[project.extra.journey]` of `zensical.base.toml`: five stages, each with its pages (URL and title), a goal and an
illustration. Every release must have the pages it lists. The template `overrides/journey.html` shows the stages;
`overrides/main.html` adds, on every page it lists, the journey bar under the title, and at the end the "Mark this page
as read" box with the previous and next steps. The progress is kept in the reader's browser only
(`overrides/assets/javascripts/learning.js`).

Every page shows a level (Discover, Practise or Master), taken from its section in `[project.extra.journey.levels]`.
A page can set another one in its front matter: `level: discover`, `practise` or `master`.

The journey adds no technical statement: its texts only say what each stage covers and link to the pages, which keep
their evidence labels.

## Definitions on hover and quizzes

**Definitions.** The first time a term of the glossary appears on a page, the reader can hover, focus or click it to
see its meaning and the section that defines it. The data is generated at build time from the table of
`docs/day2/<id>/reference/glossary.md` (`tools/site/glossary.py`, written to `docs/day2/<id>/assets/data/glossary.json`, which
is git-ignored): to add or fix a definition, edit the glossary row. A term in lower-case words ("drift", "one-shot
container") is matched in the text; any other term, the parts in parentheses and the everyday words listed in
`EVERYDAY_WORDS` of `glossary.py` ("restart"), only as a whole code span.

**Quizzes.** A page can end with a "Check yourself" block: a `quiz` list in its front matter.

```yaml
quiz:
  - q: "How is a configuration change applied to a running container?"
    options: ["The service reloads its configuration", "By a full stop and start"]
    answer: 1                    # index of the right option, from 0
    explain: "Restates what the section establishes; inline HTML such as <code> is allowed."
    see: "43-the-config--check--handler-pattern"   # anchor of the section on this page (optional)
```

A quiz only restates what the page already establishes, with the same evidence, and `see` points to the section
that gives it (check_site checks the anchor); leave `see` out on a page without sections. Every page of the learning
journey has a quiz, except the lookup pages (glossary, find it fast, command quick lookup). The answers differ between
releases when the code does: write each release's quiz from its own page.

The score counts the first choice of each question. `learning.js` keeps the best score of each page in the reader's
browser (`kolla-ansible-academy:quiz:<release>`); the journey page shows it next to the page, with a "Continue where you
left off" link (`overrides/partials/resume.html`, also on the release home) to the first page not yet marked as read.
"Reset my progress" forgets both.

`make docs-check` runs `tools/site/check_learning.py`, which checks the shape of all these blocks (answers, one `best`
choice, allowed inline HTML, `see` targets): see [tools/site/README.md](tools/site/README.md#learning-blocks-check_learningpy).

**To remember.** A page of the journey can end with a `remember` list in its front matter: 3 to 5 short sentences, the
takeaways a reader would note before a production run, each restating the page with its evidence label. They are
rendered after the page, before the scenarios and the quiz, with a button that copies them as plain text.

```yaml
remember:
  - "A tag never restricts which hosts a play targets: use <code>--limit</code> for that."
```

**Scenarios.** Before the quiz, a page can hold "What would you do?": a `scenarios` list in its front matter, each a
situation from a real platform with three possible actions.

```yaml
scenarios:
  - title: "Short title of the situation"
    situation: "Two to four sentences, in the second person."
    ask: "What would you do?"
    choices:
      - text: "One action"
        verdict: "risky"
        why: "Why, restating the page."
      - text: "Another action"
        verdict: "best"
        why: "..."
      - text: "A third action"
        verdict: "avoid"
        why: "..."
    see: "anchor-of-a-section"
```

Exactly one choice is `best`; the others are `risky` (works, with a risk the page describes) or `avoid` (contradicted
by the page). The situation may be invented, the technical facts may not: every `why` restates the page with its
evidence labels, and a destructive action on production is never the best choice. Scenarios are on the operation and
risk pages and on the Nova deep dive.

**Final challenge of a stage.** The front matter of `docs/day2/<id>/start/learning-journey.md` holds `challenges`, a quiz
per stage id of `extra.journey` (`discover`, `understand`, `practise`, `judge`, `master`). It has the format of a page
quiz, except that `see` is the path of the page that gives the answer, from the root of the release
(`risk/tags/#4-practical-consequences`). The questions cover the whole stage, at least three of its pages, and do not
repeat the quizzes of the pages. The seal of a stage lights up once its pages are marked as read and its challenge has
all answers but one right on the first try (`learning.js`, key `kolla-ansible-academy:challenge:<release>`); the seal
of the journey needs every stage seal.

## Moving a repository into a module

The single modules of [academy.toml](academy.toml) come from former OzarLand repositories, moved here one at a time
with their history, in the order of the path. One pull request per repository:

1. In a throwaway clone of the former repository, rewrite its history with
   [git filter-repo](https://github.com/newren/git-filter-repo): leave out the files this repository already has
   (`LICENSE`, `CODE_OF_CONDUCT.md`, `.gitignore`, `.github/`), rename every `README.md` to `index.md`, and move every
   path under `docs/<module>/`:

   ```bash
   git filter-repo --invert-paths --path LICENSE --path CODE_OF_CONDUCT.md --path .gitignore --path .github/
   git filter-repo --filename-callback '
   if filename == b"README.md" or filename.endswith(b"/README.md"):
       filename = filename[:-len(b"README.md")] + b"index.md"
   return b"docs/<module>/" + filename
   '
   ```

2. Here, on a branch: fetch that clone and merge it with `git merge --allow-unrelated-histories --no-ff`. The pages
   keep their history (`git log --follow docs/<module>/index.md`).
3. Set `status = "available"` for the module in academy.toml and write `docs/<module>.toml` (`site_description`,
   `nav`).
4. Run `python3 tools/site/rewrite_links.py`, read what it would change, then run it with `--apply`. It rewrites the
   links to `README.md`, to the files left out, and the absolute links to the former repositories whose module is
   available: in every module, so that a module moved earlier now links to this one. Commands in code blocks, such as
   `git clone`, are updated by hand.
5. Give each page a front matter with `title` and `description`, and fit the home page into the portal: no badges, no
   "OzarLand home" link, no table of the former repositories.
6. Copy the issue forms of the former repository into `.github/ISSUE_TEMPLATE/` (prefixed with the module when the
   name is not shared, such as `lab-failed.yml`, and listed in `FORM_RENAMES` of rewrite_links.py when renamed):
   the former repository is archived, and an archived repository takes no new issue. rewrite_links.py sends the
   links that open an issue there to this repository.
7. If the former repository ran the content checker of the hub, add the module to `MODULES` in
   [tools/site/check_content.py](tools/site/check_content.py).
8. `make docs-check STRICT=1`, `make docs-content` and `make docs-build STRICT=1`, then the pull request. The former repository is archived
   after the portal is published, with a README that points to the module.

