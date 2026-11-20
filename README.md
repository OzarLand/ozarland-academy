# OzarLand Academy

**Learn to run OpenStack, step by step.** Part of [OzarLand](https://github.com/OzarLand/ozarland): *a shared land for
better OpenStack operations.*

OzarLand Academy is one learning path in five steps. Each step is a module, with its own pages under `docs/<module>/`
and its own site in the portal:

| Step | Module | What it gives you | Sources | Status |
|---|---|---|---|---|
| Discover | Quick lab | A disposable OpenStack lab on cloud VMs in about an hour, with break-and-repair exercises | `docs/lab/` | being moved in |
| Deploy | Deployment patterns | Ways to deploy OpenStack with Kolla-Ansible, compared rather than prescribed | `docs/deploy/` | being moved in |
| Operate | Kolla-Ansible Academy | Kolla-Ansible Day-2 operations learned from the source code, one study per OpenStack release | [docs/day2/](docs/day2/2024.1/index.md) | available |
| Intervene | VM runbooks | Symptom-driven runbooks for instance and hypervisor problems | `docs/runbooks/` | being moved in |
| Go to production | Production guide | Visual memos for production: one operational lesson per page | `docs/production/` | being moved in |

The modules come from separate OzarLand repositories, moved here one at a time with their history. Until a module is
moved, the portal shows a "coming soon" page for it, and the former repository stays the place to read it.

[academy.toml](academy.toml) is the registry that every tool reads: the modules in the order of the path, and the
releases of the day-2 module.

## Portal

**<https://ozarland.github.io/ozarland-academy/>**

The portal is the recommended way to read the academy: its root is the learning path, and every module (and every
release of the day-2 module) is a site of its own, with its search, its navigation and its "recently updated" list.
The Docs workflow ([.github/workflows/docs.yml](.github/workflows/docs.yml)) rebuilds and publishes it on every push to
`main` that changes the documentation.

The address of the portal comes from one variable of the repository, `SITE_DOMAIN`: empty, the portal is published at
the address above; set to a domain name, at `https://<SITE_DOMAIN>/`. The pages only use relative links, so they do not
change when the address does. [tools/site/README.md](tools/site/README.md#address-of-the-portal) says how to switch.

## Operate: Kolla-Ansible Academy (`day2`)

The day-2 module makes learning Kolla-Ansible easier: it explains what each tag really executes, how runs scale with
the number of compute nodes, and what Kolla-Ansible commands do to a running platform, with a learning journey in five
stages for beginners. The study rests only on reading source code; nothing was run against a host ([Method and limits
of the study](docs/day2/2023.1/reference/method-and-limits.md)).

The module is organised by release of OpenStack and Kolla-Ansible. Each release is a separate study, with its own pages
under `docs/day2/<release>/` and its own site at `day2/<release>/` in the portal. Three releases are studied today,
Ussuri, 2023.1 and 2024.1:

| Release | OpenStack | Kolla-Ansible | Sources |
|---|---|---|---|
| `ussuri` | Ussuri | 10.x, tag `ussuri-eol` | [docs/day2/ussuri/](docs/day2/ussuri/index.md) |
| `2023.1` | 2023.1 Antelope | 16.x, tag `2023.1-eol` | [docs/day2/2023.1/](docs/day2/2023.1/index.md) |
| `2024.1` | 2024.1 Caracal | 18.x, tag `2024.1-eom` | [docs/day2/2024.1/](docs/day2/2024.1/index.md) |

The registry also lists the planned releases, from Victoria (Kolla-Ansible 11.x) onwards. A planned release has no
content: the portal shows it in the release selector as "coming soon" and publishes a single page that says the study
is not available yet. [Adding a release](CONTRIBUTING.md#adding-a-release) says how a release is planned, added or made
available.

This module was published until now as Kolla-Ansible Academy, in the repository `OzarLand/kolla-ansible-academy`; its
history continues here.

### Versions studied: Ussuri

| Component | Version |
|---|---|
| OpenStack release | Ussuri (`openstack_release: "ussuri"`, `ansible/group_vars/all.yml:530`) |
| Kolla-Ansible | 10.x series, the Ussuri series: tag `ussuri-eol`, commit `8a94fe9`. The last numbered release tag of the series in `openstack/kolla-ansible` is `10.4.0`; `ussuri-eol` is a later commit |
| Kolla (images) | tag `ussuri-eol` of `openstack/kolla` |
| Ansible | 2.9.27 |

All conclusions come from the Ussuri implementation, not from newer releases.

### Versions studied: 2023.1

| Component | Version |
|---|---|
| OpenStack release | 2023.1 Antelope (`openstack_release: "2023.1"`, `ansible/group_vars/all.yml:578`) |
| Kolla-Ansible | 16.x series: tag `2023.1-eol`, commit `4891a21` |
| Kolla (images) | tag `2023.1-eol` of `openstack/kolla`, commit `de82941` |
| ansible-collection-kolla | tag `2023.1-eol` (`requirements.yml` pins `unmaintained/2023.1`); it holds the `bootstrap-servers` roles |
| Ansible | ansible-core 2.14.18 (`tools/kolla-ansible:10-11` accepts 2.13 to 2.14) |

The 2023.1 pages were re-studied from the Ussuri study: every Ussuri citation was looked up in the 2023.1 sources and
every statement re-checked against them; [Method and limits](docs/day2/2023.1/reference/method-and-limits.md) says what
does not carry over.

### Versions studied: 2024.1

| Component | Version |
|---|---|
| OpenStack release | 2024.1 Caracal (`openstack_release: "2024.1"`, `ansible/group_vars/all.yml:679`) |
| Kolla-Ansible | 18.x series: tag `2024.1-eom`, commit `890396f` |
| Kolla (images) | tag `2024.1-eom` of `openstack/kolla`, commit `ed7a36a` |
| ansible-collection-kolla | tag `2024.1-eom`, commit `82a0f5c` (`requirements.yml` pins `stable/2024.1`) |
| Ansible | ansible-core 2.16.20 (`tools/kolla-ansible:10-11` accepts 2.15 to 2.16) |

The 2024.1 pages were re-studied from the 2023.1 study in the same way: every 2023.1 citation was looked up in the
2024.1 sources and every statement re-checked against them; [Method and limits](docs/day2/2024.1/reference/method-and-limits.md)
says what changed, and [research/2024.1/](research/2024.1/README.md) keeps the change map used for the re-study.

### How the content of a release is organised

The tabs of the Ussuri release:

| Tab | What it holds |
|---|---|
| [Home](docs/day2/ussuri/index.md) | Entry page, [Find it fast](docs/day2/ussuri/start/find-it-fast.md), [Ten things to know before a production run](docs/day2/ussuri/start/ten-things-to-know.md), [Conventions and evidence labels](docs/day2/ussuri/start/conventions.md) |
| [Operations](docs/day2/ussuri/operations/index.md) | One page per Day-2 operation, with its commands, its impact classes and the risks it names |
| [Troubleshooting](docs/day2/ussuri/troubleshooting/index.md) | Symptom index, known bugs and limitations, open questions, what is not known |
| [Components](docs/day2/ussuri/components/index.md) | One page per OpenStack service and per infrastructure component, each ending with its service card |
| [Risk and impact](docs/day2/ussuri/risk/index.md) | The 25 rated risks, what a tag really executes, the tag index |
| [Concepts](docs/day2/ussuri/concepts/index.md) | Repository architecture, deployment execution flow, compute scaling, the kolla images |
| [Reference](docs/day2/ussuri/reference/index.md) | Findings, glossary, generated inventory, per-role fact sheets, Ansible listings, method and limits |

### Evidence labels

- **[CODE]** shown by the sources, with a `path:line` citation nearby.
- **[NOT AVAILABLE]** the sources do not establish it.

The full definition is in [Evidence labels](docs/day2/ussuri/start/conventions.md#evidence-labels).

## Build and check locally

Needed: Python 3.11 or newer, `git`, `make`. Only `make docs-deps` needs the network.

```bash
python3 -m venv .venv     # once; the Makefile uses .venv when it exists, no activation needed
make docs-deps
make docs-check
make docs-build
make docs-serve           # one site, rebuilt on change: http://localhost:8000/ozarland-academy/day2/2024.1/
make docs-preview         # the built portal, every site: http://localhost:8000/ozarland-academy/
```

| Target | What it does |
|---|---|
| `make docs-deps` | Installs the pinned build dependencies (`requirements-docs.txt`) and fetches the vendored Mermaid bundle |
| `make docs-check` | Checks the Markdown sources; no build needed |
| `make docs-build` | Runs the unit tests of `tools/site`, the strict build of every site and of the portal root into `site/`, then the checks on the built portal |
| `make docs-test` | Runs the unit tests of `tools/site` only |
| `make docs-serve` | Serves a live preview of one site |
| `make docs-preview` | Serves the built portal the way GitHub Pages publishes it |
| `make docs-clean` | Removes what the build generates |

`RELEASE=<path>` (such as `day2/2024.1`) limits `docs-check` and `docs-build` to one site and chooses the site of
`docs-serve`. `SITE_DOMAIN=<domain>` builds the portal for that address. `STRICT=1` reports the warnings of the checks
as errors, `PYTHON=<interpreter>` forces an interpreter and `DEV_ADDR=<ip:port>` moves the preview. The rules of the
checks and the CI workflow are described in [tools/site/README.md](tools/site/README.md).

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) says where a page goes, how it is built, which evidence is accepted, how a release
is added and which checks to run before a pull request.

## Tools

- [tools/extract_kolla_inventory.py](tools/extract_kolla_inventory.py) writes the generated inventory of a release of
  the day-2 module ([docs/day2/ussuri/reference/generated-inventory.md](docs/day2/ussuri/reference/generated-inventory.md))
  from a Kolla-Ansible checkout.
- [tools/service_cards.py](tools/service_cards.py) rewrites the service cards of the component pages of a release
  (`docs/day2/ussuri/components/`), between their `GENERATED` markers.
- Both take `--release <id>`; without it they write into the default release of the day-2 module.
- [tools/site/](tools/site/README.md) holds the site tooling: the registry, the build, the checks, the pre-build step
  and the local Markdown extension.

## Licence

Apache License 2.0, see [LICENSE](LICENSE).
