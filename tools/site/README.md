# Site tooling

The portal of OzarLand Academy is generated from the Markdown under `docs/` by
[Zensical](https://github.com/zensical/zensical) 0.1.2. This directory holds what the build needs besides the
generator: the registry of modules and releases, the build, the checks, the pre-build step and the local Markdown
extension.
Nothing here holds content.

| File | Role |
|---|---|
| [releases.py](releases.py) | Reads `academy.toml`, gives the address of the portal (`SITE_DOMAIN`), writes the configuration Zensical builds for each site and for the root of the portal, and assembles the root (learning path, home of the versioned module, `versions.json`, not-found page, pages of the planned modules and releases, `CNAME`). Standard library only. |
| [build.py](build.py) | Runs the whole build: `prebuild.py`, Zensical for each available site, Zensical for the root, then the assembly. Also starts the live preview of one site. |
| [check_docs.py](check_docs.py) | Checks on the registry and on the Markdown sources of every available site. No build needed, standard library only. |
| [check_learning.py](check_learning.py) | Checks the learning blocks of the front matter (`remember`, `scenarios`, `quiz`, `challenges`): shape, answers, one "best" choice, allowed inline HTML, `see` targets. Needs PyYAML, a pinned dependency. |
| [check_site.py](check_site.py) | Checks on the built portal. Standard library only. |
| [prebuild.py](prebuild.py) | Writes `docs/<path>/assets/data/updates.json` for each available site (date of the last change of each page) and makes sure the vendored Mermaid bundle is in place. |
| [fetch_vendor.py](fetch_vendor.py) | Downloads the pinned Mermaid bundle to `overrides/assets/vendor/mermaid/mermaid.min.js` and verifies its checksums. The file is not committed. |
| [serve_site.py](serve_site.py) | Serves the built portal locally under the path of its address, with the root `404.html` for unknown addresses, as GitHub Pages does. |
| `portal_mdx/` | Python-Markdown extension enabled in `zensical.base.toml`. The build finds it through `PYTHONPATH=tools/site`. |
| `tests/` | Unit tests of the files above (`unittest`). |

Related files at the root of the repository: [Makefile](../../Makefile),
[requirements-docs.txt](../../requirements-docs.txt), [academy.toml](../../academy.toml),
[zensical.base.toml](../../zensical.base.toml), `overrides/` and
[.github/workflows/docs.yml](../../.github/workflows/docs.yml).

## Modules and releases: layout of the sources and of the portal

OzarLand Academy is one learning path in five steps; each step is a **module**. A module is either one site
(`kind = "single"`) or, for the day-2 module, one site per OpenStack release (`kind = "versioned"`). Every site is
self-contained and published under its own URL prefix, its *path*: `<module>/` or `<module>/<release>/`. So the search,
the navigation and the "recently updated" list of a site cover that site only, and adding a module or a release never
moves an existing address. How to add a release is in [CONTRIBUTING.md](../../CONTRIBUTING.md#adding-a-release).

| Source | What it is |
|---|---|
| `academy.toml` | The registry: one `[[module]]` block per module, in the order of the path (`id`, `step`, `title`, `summary`, `kind`, and `status` or `default`), and for the versioned module one `[[module.release]]` block per release (`id`, `status`, `openstack`, `kolla_ansible`, `tag`, optional `title`). Every tool reads it; nothing else lists the modules or the releases. |
| `zensical.base.toml` | The site configuration shared by all sites: theme, palette, Markdown extensions, validation, the default address of the portal root. It is not given to Zensical as it is. |
| `docs/<path>/` | The Markdown of an available site: `docs/<module>/` or `docs/day2/<release>/`. |
| `docs/<path>.toml` | The settings of that site: `site_description` and `nav`. Its `[project]` table is merged over the one of `zensical.base.toml`: tables are merged, lists and plain values replace those of the base. |
| `overrides/` | The templates, and under `overrides/assets/` the static files shared by all sites: stylesheet, scripts, logo, favicon, vendored Mermaid. `overrides/` is the theme directory (`custom_dir`), and Zensical copies the static files of the theme directory into every site it builds, so these files exist once in the repository. |

A single module and a release are `available` or `planned`. A planned one has no `docs/<path>/` and no
`docs/<path>.toml`. Only one module can be versioned: the release selector of the header serves that module.

The learning kit of a release (the learning journey of `extra.journey`, the levels, the districts of the island with
their banners and tab icons, the definitions on hover, Lumo's notes) is built for the versioned module only: its
pages follow the sections it expects. A single module is a plain site: its configuration has no `extra.journey`, and
its home page gets the module header of the art direction (breadcrumb, stage seal, section band, next stop) from
`overrides/main.html`.

What the build writes (all git-ignored):

| Path | Content |
|---|---|
| `.zensical.<name>.toml` | Configuration of one available site (`<name>` is the path with `/` replaced by `_`, such as `day2_2024.1`): base and site settings merged, then `docs_dir = "docs/<path>"`, `site_dir = "site/<path>"`, `site_url = "<portal address><path>/"`, `edit_uri = "blob/main/docs/<path>/"`, `site_name` (the title of the module) and `extra.portal` (the modules and releases of the registry, read by the templates). `edit_uri` and `site_name` may be set in `docs/<path>.toml`; `docs_dir`, `site_dir` and `site_url` may not. |
| `.zensical._root.toml`, `.build/root/` | Configuration, Markdown stubs and output of the root site: the learning path, the home of the versioned module, the not-found page and one page per planned module or release. The text of these pages is in the templates `overrides/academy.html`, `overrides/landing.html`, `overrides/planned.html` and `overrides/404.html`; the stubs only carry a title. |
| `docs/<path>/assets/data/updates.json` | Written by `prebuild.py`. |
| `site/<path>/` | Site of an available module or release. |
| `site/<path>/index.html` | The only page of a planned module or release ("coming soon"). |
| `site/index.html` | The learning path (overrides/academy.html): the modules in order, a planned one marked "coming soon". |
| `site/day2/index.html` | Home of the day-2 module (overrides/landing.html): why it exists, a suggested learning path in the default release, and the list of the releases. |
| `site/day2/versions.json` | The releases of the module as JSON, in the form the tool `mike` writes (`version`, `title`, `aliases`), with `status`, `default`, `openstack`, `kolla_ansible` and `tag` under `properties`. No page of the portal needs it; it is there for scripts and other tools. |
| `site/404.html` | Not-found page of the whole portal (GitHub Pages serves it for every unknown address). See below. |
| `site/sitemap.xml` | Index of the sitemaps of the available sites (`site/<path>/sitemap.xml`). |
| `site/CNAME` | The custom domain, when `SITE_DOMAIN` is set. See [Address of the portal](#address-of-the-portal). |
| `site/assets/` | Theme files used by the root pages. |

The generated configurations are at the root of the repository because Zensical only accepts a `docs_dir` inside the
directory of its configuration file, and its TOML format has no include.

### Addresses

- A page of a site: `<portal address><path>/<page>/`, for example
  `https://ozarland.github.io/ozarland-academy/day2/ussuri/operations/reconfigure-nova/`. The canonical link, the
  sitemap and "View source" (`blob/main/docs/<path>/<page>.md`) follow.
- The root address is the learning path. `day2/` is the home of the day-2 module; its main button opens the default
  release.
- Any address under a planned module or release leads to its one page, `/<path>/`.
- Anything else shows the not-found page, which lists the modules and the releases.
- The addresses of the former site, `https://ozarland.github.io/kolla-ansible-academy/…`, are not handled here: that
  site redirects them itself, once the portal has its final address.

### Address of the portal

The address of the portal root comes from one place, `releases.portal_root_url()`:

- the environment variable `SITE_DOMAIN` empty or unset: `site_url` of `zensical.base.toml`,
  `https://ozarland.github.io/ozarland-academy/`;
- `SITE_DOMAIN` set to a domain name (no scheme, port or path): `https://<SITE_DOMAIN>/`, and the build writes
  `site/CNAME`.

In CI, `SITE_DOMAIN` is the repository variable of the same name (**Settings**, **Secrets and variables**,
**Actions**, **Variables**), read by the `build` job. The address sets the canonical links, the sitemaps, the
not-found page and the social preview image; the pages themselves only have relative links, so the same Markdown
works at any address. `check_docs.py` enforces that (rule `link-site-address`): no page writes an address of the
portal, and `README.md`, `CONTRIBUTING.md` and this file write only the current one.

To build or check for a domain locally: `make docs-build SITE_DOMAIN=academy.example.org`, or
`python3 tools/site/releases.py url` to print the address the tools use.

GitHub Pages ignores `CNAME` when the site is deployed by a workflow, as here: the custom domain itself is set in
**Settings**, **Pages**, **Custom domain**. Switching to a domain is, in this order:

1. Verify the domain for the organization (organization **Settings**, **Pages**, **Verified domains**), so that no
   other repository can use it.
2. Create the DNS records: `A` and `AAAA` records of the domain to the addresses of GitHub Pages, and a `CNAME`
   record `www` to `ozarland.github.io`.
3. Open a pull request that writes the new address in `README.md` (the rule `link-site-address` fails until the
   variable and the files agree), set the variable `SITE_DOMAIN`, set the custom domain in **Settings**, **Pages**,
   re-run the checks of the pull request, and merge it.
4. Tick **Enforce HTTPS** once the certificate is issued. GitHub then redirects the former `github.io` address to the
   domain.

### Release selector

The header of every page shows the release being read and, when the registry has more than one release, a list of all
of them: the available ones, then the planned ones under "Coming soon". The markup is
`overrides/partials/releases.html`, written into each page from `extra.portal`: without JavaScript every entry is a
plain link to the home page of a release. `portal.js` adds two things: Escape or a click outside closes the list, and
a link to another available release opens the page being read in that release when the `updates.json` of that
release lists it, and its home page otherwise. A planned release always opens its "coming soon" page.

The version selector that the theme has for sites published with `mike` is not used (`extra.version` is not set). It
does read a plain `versions.json` at the portal root, and it does switch to the same page, but it draws the list
inside the title area of the header, where this theme variant clips it; it disappears as soon as the page is
scrolled, because the title area then shows the page title; it shows nothing without JavaScript; and it cannot mark a
release as planned.

`overrides/partials/header.html` is a copy of the header of the theme with the selector added, and without drawer
button, search and tabs on the root pages. Compare it with the file of the theme when Zensical is upgraded.

## Build locally

Needed: Python 3.11 or newer (CI uses 3.13), `git`, `make`. Only `make docs-deps` needs the network: PyPI for the
build dependencies and `registry.npmjs.org` for the Mermaid bundle.

```bash
python3 -m venv .venv     # once; the Makefile uses .venv when it exists, no activation needed
make docs-deps
make docs-check
make docs-build
make docs-serve           # one site, rebuilt on change: http://localhost:8000/ozarland-academy/day2/2024.1/
make docs-preview         # the built portal, every site: http://localhost:8000/ozarland-academy/
```

Without `.venv` the Makefile runs `python3` from `PATH`, which is what CI does. `make PYTHON=/path/to/python ...`
forces another interpreter.

| Target | What it runs |
|---|---|
| `docs-deps` | `pip install -r requirements-docs.txt`, then `fetch_vendor.py`. |
| `docs-check` | `check_docs.py`: the registry and every available site; then `check_learning.py`: the learning blocks of the front matter. |
| `docs-build` | The unit tests of `tests/`, then `build.py --strict` (`prebuild.py`; `zensical build --clean --strict` for each available site into `site/<path>/`; the same for the root site; the assembly of the root into `site/`), then `check_site.py site`. |
| `docs-test` | The unit tests of `tests/` only (`python3 -m unittest discover -s tools/site/tests`). |
| `docs-serve` | `build.py --serve`: `prebuild.py`, then `zensical serve` for one site (rebuilds on change). The preview holds that site only: links to other sites do not work there. `DEV_ADDR=127.0.0.1:8001` moves it. |
| `docs-preview` | `serve_site.py site`: the built portal under the path of its address, with the root `404.html` for unknown addresses. Use it to try the release selector and the pages of the planned modules. Run `make docs-build` first. |
| `docs-clean` | Removes `site/`, `.cache/`, `.build/`, the generated `.zensical.*.toml`, the `updates.json` of every site and the `__pycache__` directories under `tools/`. The Mermaid bundle stays. |

`RELEASE=<path>` limits a target to one available site, named by its path (`day2/ussuri`, `lab`) or, when it is
unique, by its last segment (`ussuri`): `make docs-check RELEASE=day2/ussuri` checks that site (and the registry);
`make docs-build RELEASE=day2/ussuri` rebuilds that site and the root, leaves the other sites as they are in `site/`,
and does not fail on a link to a site that is not built; `make docs-serve RELEASE=day2/ussuri` chooses the site of the
preview (default: the default release of the day-2 module). Without `RELEASE`, `docs-build` empties `site/` first and
builds everything.

`SITE_DOMAIN=<domain>` builds and checks the portal for that address (see [Address of the portal](#address-of-the-portal)).

`STRICT=1` (`make docs-check STRICT=1`, `make docs-build STRICT=1`) passes `--strict` to both check scripts:
their warnings become errors. CI runs both targets with `STRICT=1`, so run them the same way before opening a pull
request.

`site/`, `.cache/`, `.build/`, `.zensical.*.toml`, `.venv/`, `docs/<path>/assets/data/updates.json` and the Mermaid
bundle are generated or downloaded. They are listed in `.gitignore` and must not be committed.

## Source checks: check_docs.py

The script reads `academy.toml`, then, for every available site, the Markdown pages under `docs/<path>/` and the
`nav` of `docs/<path>.toml` (`--release <path>`: that site only). It also checks the links of `README.md`,
`CONTRIBUTING.md` and this file. It prints the findings by file with their line, then a summary, and exits with 1
when there is at least one error. On GitHub Actions each error is also an annotation on the file.

| Rule | Level | What is checked |
|---|---|---|
| `registry` | error | `academy.toml` can be read (modules, kinds, ids, statuses, the `default` of the versioned module, a `tag` for each available release) and matches the tree: an available site has `docs/<path>/` and `docs/<path>.toml`, a planned one has neither, and nothing else sits directly under `docs/` or under the directory of the versioned module. |
| `encoding` | error | The file is UTF-8. |
| `front-matter` | error | The page starts with a front matter block that can be read. |
| `title` | error | The front matter has a non-empty `title`. |
| `description` | error | `description` is not empty and has at most 160 characters. A missing `description` is a warning. |
| `impact` | error | Every `impact` value is one of `read-only`, `writes-config`, `pulls-images`, `restarts-on-drift`, `recreates-containers`, `critical`, `maintenance-window`, `recovery`. |
| `tags` | warning | `tags` is a list of lowercase names. |
| `link-file` | error | The target of a relative link or image exists, with the same letter case. |
| `link-anchor` | error | The fragment of a link is a heading anchor of the target or an explicit `id` (for example `<a id="r12"></a>`). |
| `link-style` | error | Links between pages of a site are relative, stay inside the site (`docs/<path>/`) and point to a `.md` file, not to a directory. |
| `link-site` | error | A link to another site of the portal (another module, another release) is the address of its page relative to the file, ending with `/`, such as `../../2023.1/start/conventions/` from `docs/day2/2024.1/start/`: each site is built on its own, so a link to the `.md` file of another site fails the build, while Zensical keeps a relative address and adjusts it to the published page. The site is in the registry, the page exists in its sources, and so does the anchor (reported as `link-anchor`). For a planned site only its home address is accepted. `../../` from the top of a release, or `../` from the top of a module, is the home of the day-2 module or the learning path. |
| `link-site-address` | error | No page writes an address of the portal (the current one, `site_url` of `zensical.base.toml`, or a former one such as `ozarland.github.io/kolla-ansible-academy`), as a link, an autolink or plain text outside code: the site must work at any address. `README.md`, `CONTRIBUTING.md` and this file may write the current address only. |
| `link-reference` | error | A reference-style link `[text][label]` uses a label defined in the file. |
| `link-repo-file` | error | An absolute link to a file of this repository on `main` points to a file that exists. |
| `code-language` | error | Every fenced code block has a language and is closed. |
| `removed-path` | error | No reference to a path of the former layout (`annex/`, `docs/01-...` to `docs/10-...`), in the pages of the versioned module (the only one that had it). Inside an HTML comment it is a warning. |
| `callout` | error | Callouts are GitHub alerts of the five types `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, with the marker alone on the first line of the blockquote. |
| `todo-editorial` | warning | No `<!-- TODO editorial` marker is left. |
| `nav` | error | Every page of a site is listed in the `nav` of `docs/<path>.toml`, and every `nav` entry exists, once. |
| `config` | error | `zensical.base.toml` and `docs/<path>.toml` exist and can be read, and `SITE_DOMAIN` is a domain name. |

Heading anchors are computed the way github.com computes them: lowercase, every character that is not a letter,
a digit, an underscore, a hyphen or a space is dropped, each space becomes a hyphen, and a repeated heading gets
`-1`, `-2`. Lines inside fenced code are not headings. `zensical.base.toml` configures the site to produce the same
anchors, so a link that passes here works on github.com and on the site.

```bash
python3 tools/site/check_docs.py              # warnings do not fail the run
python3 tools/site/check_docs.py --strict     # warnings are errors
python3 tools/site/check_docs.py --release day2/ussuri
python3 tools/site/check_docs.py --list-rules
```

## Content conventions of the hub: check_content.py

The pages of Deployment patterns (`deploy`) and VM runbooks (`runbooks`) follow the community content conventions of
the OzarLand hub: a `kind` in the front matter (`pattern`, `runbook`...), the fields and sections each kind requires,
risk markers that match the declared `risk`, and no sensitive data (addresses outside the documentation ranges,
secrets). Their former repositories checked them with the hub's `tools/check_content.py`; so does this repository.

```bash
git clone https://github.com/OzarLand/ozarland.git ../ozarland
make docs-content HUB=../ozarland
```

`tools/site/check_content.py` loads the hub's checker and runs it on `docs/<module>/` of each available module of the
two. `index.md` (the former `README.md`) is the index of its directory, not a page with a `kind`; links are left to
`check_docs.py`, which also resolves the links between modules. The other modules never followed these conventions
and are not checked.

## Learning blocks: check_learning.py

The quizzes, scenarios, "To remember" cards and final challenges live in the front matter of the pages (format:
[CONTRIBUTING.md](../../CONTRIBUTING.md#definitions-on-hover-and-quizzes)). `check_learning.py` parses them with PyYAML
and fails on: an unknown key or a wrong type; an `answer` that is not an index of `options`; a scenario without
exactly one `best` choice among three, or with another verdict than `best`, `risky`, `avoid`; a `remember` list
outside 3 to 5 items; a text with Markdown backticks, a bracketed `[CODE]`/`[NOT AVAILABLE]` label, a tag other than
`<code>`, `<strong>`, `<em>` and the evidence chips, or an unbalanced tag; a quiz or scenario `see` that is not a bare
anchor (check_site then checks that the anchor exists); `challenges` outside `start/learning-journey.md`, a stage id
missing or unknown, or a challenge `see` whose page has no Markdown source in the release.

```bash
python3 tools/site/check_learning.py
python3 tools/site/check_learning.py --release day2/2023.1
```

## Built-portal checks: check_site.py

`zensical build --strict` already fails on a broken link or anchor in the Markdown. `check_site.py` looks at the
files written to `site/`, whatever produced them (Markdown, templates of `overrides/`, the theme, `releases.py`). It
reads the whole portal at once, so a link from one site to another, such as those of the release selector, is
checked like any other link.

On every page of the portal:

| Rule | Level | What is checked |
|---|---|---|
| `link-file` | error | Every internal `href` and `src` of every HTML page, and every `url()` of every stylesheet, points to a file of the portal. |
| `link-anchor` | error | Every internal link with a fragment points to an element `id` of the target page. |
| `external-resource` | error | No page or stylesheet loads a script, a stylesheet, a font, an image or a frame from another origin. Plain `<a href>` links to other sites are allowed and their hosts are listed in the summary. |
| `runtime-request` | error | Nothing makes the theme script call another host in the browser: a page with a Mermaid diagram loads the vendored Mermaid library, and no element requests the GitHub repository statistics. Loading Mermaid on a page without a diagram is a warning. |
| `page-empty` | error | No page has an empty content area. A page with a title and no other text is a warning. |
| `canonical` | error | The canonical address of a page is the address of that page, under the prefix of its site. |
| `duplicate-id` | warning | An `id` is used twice in a page. |

On each available site (`site/<path>/`):

| Rule | Level | What is checked |
|---|---|---|
| `page-missing` | error | Every Markdown page under `docs/<path>/` has its built page. |
| `search-index` | error | `<path>/search.json` exists, is valid JSON, has at least one entry per page, and every entry points to an existing page and anchor of the same site. |
| `sitemap` | error | Every URL of `<path>/sitemap.xml` is a page of that site. |
| `updates` | error | Every entry of `<path>/assets/data/updates.json` is a built page. |

On the root of the portal:

| Rule | Level | What is checked |
|---|---|---|
| `portal-root` | error | The learning path lists the modules of `academy.toml` in their order, and its call to action opens the first available module (`data-portal-start`). Every module has its home page. The home of the versioned module links to its default release (`data-portal-default`), that release is built, and `<module>/versions.json` is valid JSON and says what `academy.toml` says. The not-found page knows the same sites with the same statuses. Every available site is built. Every planned module or release has its page, which names it and says that it is not available yet, and has no other file. No directory of `site/` belongs to no module or release. |

The summary gives, for each site, the number of pages built and of search entries, then the number of pages,
internal links, links with an anchor and element ids of the portal, and the hosts of the external links.

```bash
python3 tools/site/check_site.py site
python3 tools/site/check_site.py site --strict
python3 tools/site/check_site.py site --release day2/ussuri    # after a build with --release
```

## Continuous integration

[.github/workflows/docs.yml](../../.github/workflows/docs.yml) runs on pull requests and on pushes to `main` that
change `docs/`, `overrides/`, `tools/site/`, `academy.toml`, `zensical.base.toml`, `requirements-docs.txt`,
`Makefile` or the workflow itself (pull requests: also `README.md` and `CONTRIBUTING.md`, whose links are checked). It can also be started by
hand (Actions, "Docs", "Run workflow").

| Job | When | What it does |
|---|---|---|
| `build` | Always | Full-history checkout (the "Last updated" dates come from the Git history), Python 3.13, `make docs-deps`, `make docs-check STRICT=1`, a checkout of the hub `OzarLand/ozarland` and `make docs-content`, `make docs-build STRICT=1`, with `SITE_DOMAIN` set from the repository variable of the same name. One run covers every site of `academy.toml` and the root of the portal; adding a module or a release needs no change of the workflow. |
| `production` | Always | In `docs/production/`: `npm ci`, Playwright Chromium, `node scripts/build.cjs --runbooks ../runbooks` (validates the memos, checks their runbook references against `docs/runbooks/`, renders each memo), then `git diff --exit-code` on the generated pages. |
| `deploy` | Push to `main`, or manual run on `main`, after `build` and `production` succeeded | `actions/configure-pages`, then `actions/deploy-pages` to the `github-pages` environment. |

- Both check scripts run with `--strict`: a warning (a missing `description`, a leftover `<!-- TODO editorial`
  marker, a duplicate `id` in a built page) fails the `build` job like an error.
- A pull request is never deployed. Its built portal is uploaded as the artifact `site`, kept 7 days: download it
  from the page of the run, unpack it and serve it with `python3 tools/site/serve_site.py <unpacked directory>`
  (a path relative to the repository root, or an absolute path).
- On `main` the `build` job uploads the Pages artifact that `deploy` publishes. The artifact is kept 1 day (the
  default of `actions/upload-pages-artifact`).
- The workflow token is read-only (`contents: read`). Only the `deploy` job gets more: `pages: write` and
  `id-token: write`.
- The pip download cache is keyed on `requirements-docs.txt`. The Mermaid bundle is cached with a key computed
  from `fetch_vendor.py`, which pins its version and checksums; `fetch_vendor.py` verifies the file in both cases.
- A newer commit on a pull request cancels the run in progress for that pull request. On `main` a run that has
  started always finishes, deployment included, and the next one waits. If several runs are waiting, only the newest
  is kept.

Actions used. The workflow references each one by the full commit of the version shown, with the version in a
comment: with a version tag such as `@v4`, every run in this repository ended with the conclusion `startup_failure`
before any job started, and the same step referenced by commit started.

| Action | Version |
|---|---|
| `actions/checkout` | `v7` |
| `actions/setup-python` | `v6` |
| `actions/cache` | `v6` |
| `actions/upload-artifact` | `v7` |
| `actions/upload-pages-artifact` | `v5` |
| `actions/configure-pages` | `v6` |
| `actions/deploy-pages` | `v5` |

### One-time setup: enable GitHub Pages

A repository administrator does this once:

1. Open **Settings**, then **Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

GitHub creates the `github-pages` environment and, by default, limits its deployments to the default branch. The
workflow deploys from `main`, which must stay the default branch or be added under **Settings**, **Environments**,
**github-pages**, **Deployment branches**.

For a private repository:

- GitHub Pages needs a paid plan: GitHub Pro for a repository owned by a personal account, GitHub Team or GitHub
  Enterprise for a repository owned by an organization. With GitHub Free, Pages is offered for public repositories
  only.
- The published site is public even though the repository is private. Restricting the site to people who can read
  the repository requires GitHub Enterprise Cloud and a repository owned by an organization.

The other way is to make the repository public: Pages is then available with every plan.

The expected address is `https://ozarland.github.io/ozarland-academy/`, the `site_url` of `zensical.base.toml`, as
long as the repository variable `SITE_DOMAIN` is empty. To publish on a custom domain, follow
[Address of the portal](#address-of-the-portal).

After the setup, start a deployment: use "Run workflow" on `main` (Actions, "Docs"), or push a change of the site
to `main`. Re-running only the failed `deploy` job of an earlier run works while the Pages artifact of that run
still exists (1 day); after that, re-run all the jobs of the run.

### Before GitHub Pages is enabled

- Pull requests are not affected: they only run `build`.
- On `main`, `build` passes and uploads the Pages artifact. `deploy` then fails at its first step, "Check the
  GitHub Pages configuration" (`actions/configure-pages`), with this error:

  ```text
  Get Pages site failed. Please verify that the repository has Pages enabled and configured to build using GitHub Actions, or consider exploring the `enablement` parameter for this action.
  ```

  The message ends with the error returned by the GitHub API. Nothing is published and the run on `main` is
  marked as failed until the setup above is done.
- The workflow does not enable Pages itself: the `enablement` option of `actions/configure-pages` requires a token
  other than the workflow token (`GITHUB_TOKEN`), and the workflow uses no other token.

## Maintenance

- **Warnings as errors in CI.** CI runs `make docs-check STRICT=1` and `make docs-build STRICT=1`: every warning
  of the two check scripts fails the build. Without `STRICT=1`, which is the default of the Makefile, warnings are
  printed and do not fail the run.
- **Upgrading Zensical.** `requirements-docs.txt` pins Zensical and every package it depends on. Install the new
  version in an empty virtual environment, replace the pins with the output of `pip freeze`, then run
  `make docs-deps docs-check docs-build` and look at a few pages with `make docs-serve`. Compare
  `overrides/partials/header.html` with `partials/header.html` of the new theme (it is a copy with the release
  selector added), and try the release selector, a planned module and a planned release with `make docs-preview`.
- **Upgrading Mermaid.** See `overrides/assets/vendor/mermaid/README.md`. Changing `fetch_vendor.py` changes the cache
  key in CI.
- **Upgrading the actions.** The workflow references each action by commit. To upgrade, replace the commit with
  the one of the new version tag and update the comment, one action at a time, and read the release notes for
  changed inputs.
- **Required status checks.** The workflow only runs when one of the listed paths changes. If the `build` job is
  made a required check in a branch protection rule, a pull request that touches none of these paths waits for a
  check that never starts. Either leave the check optional or remove the `paths` filter of `pull_request`.
- **Private repository.** Runs on GitHub-hosted runners count against the Actions minutes of the account.
