---
template: home.html
title: Kolla-Ansible Academy
description: "Source-level study of Kolla-Ansible 16.x (OpenStack 2023.1, tag 2023.1-eol): what each tag really executes and what commands do to a running platform."
tags: [reconfigure, deploy, tags, risk, evidence, unknowns]
---

# Kolla-Ansible Academy

## Start from what you need

<div class="grid cards" markdown>

- **[I am about to run a command](operations/index.md)**

    ---

    Operations: one page per Day-2 operation, with its commands, its impact classes and the risks it names.

- **[A run did something unexpected](troubleshooting/index.md)**

    ---

    Troubleshooting: where to start during an incident. A symptom index, the known bugs and limitations, the open
    questions, and what is not known.

- **[I need the facts about one component](components/index.md)**

    ---

    Components: one page per OpenStack service and per infrastructure component, each ending with its service card.

- **[I need to judge the risk of a change](risk/index.md)**

    ---

    Risk and impact: the 25 rated risks (R25 does not apply to 2023.1), what a tag really executes, and why a small
    change creates a large workload.

- **[I want to understand how a run works](concepts/index.md)**

    ---

    Concepts: repository architecture, deployment execution flow, compute scaling, and what the kolla images do at
    container start.

- **[I need the detailed evidence](reference/index.md)**

    ---

    Reference: findings, glossary, generated inventory, per-role fact sheets, Ansible listings, and the method and
    limits of the study.

</div>

Seven operator situations, from an incident to a failed VM deployment, are mapped to the pages to open first in [Start
from a situation](start/find-it-fast.md#start-from-a-situation).

## Frequently used procedures

The operation pages that [Find it fast](start/find-it-fast.md) and [Ten things to know before a production
run](start/ten-things-to-know.md) point to most often:

- [Reconfigure a single service](operations/reconfigure-a-service.md) — what a single-service reconfigure such as
  `-t keystone` runs, and what the tag also touches
- [Reconfigure Nova](operations/reconfigure-nova.md) — what `-t nova reconfigure` runs on the controllers and on every
  compute
- [Write config first, apply in controlled batches](operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch, or a rolling `reconfigure` with `ANSIBLE_SERIAL`
- [Update container images](operations/update-container-images.md) — how `pull`, `deploy`, `reconfigure` and `upgrade`
  treat images
- [Add a compute node](operations/add-a-compute-node.md) — the three commands with `--limit`, and what
  `deploy --limit` touches on the other hosts

Every operation page is in the [Operations catalogue](operations/index.md#operations-catalogue), and the [Command quick
lookup by tag](operations/command-quick-lookup.md) has one row per command and tag.

## Before any production run

- [Pre-execution checklist](operations/pre-execution-checklist.md) — the eight checks to make before every production
  run
- [Predict and inspect a run](operations/predict-a-run.md) — the commands that show what a run would target, render
  and restart
- [Ten things to know before a production run](start/ten-things-to-know.md) — ten points, most of them with the
  section that gives the evidence

## Recently updated

<div data-portal-recent="8" markdown>

Every change is in the
[commit history of the repository](https://github.com/OzarLand/ozarland-academy/commits/main/docs/day2/2023.1).

</div>

## How to read this portal

Every statement carries one of two evidence labels, defined in [Evidence
labels](start/conventions.md#evidence-labels):

- [CODE] shown by the sources, with a `path:line` citation nearby.
- [NOT AVAILABLE] the sources do not establish it.

An operation page shows its impact classes under its title. A class says that at least one command of the page has that
impact, not that all do. The classes and the sections that support each one are in [Operation impact
classes](start/conventions.md#operation-impact-classes):

- `read-only` — the corpus says the command changes nothing.
- `writes-config` — the command renders config and restarts no Docker container.
- `pulls-images` — the command downloads images; running containers do not change.
- `restarts-on-drift` — the command can restart containers, only if drift is detected.
- `recreates-containers` — the command recreates containers (stop, rm, create, start) when their image or parameters
  differ.
- `critical` — the page covers an operation rated Critical in the risk register.
- `maintenance-window` — the corpus asks to plan the operation as a maintenance.
- `recovery` — the page is a backup or recovery procedure.

[Find it fast](start/find-it-fast.md) lists typical operator questions and the section that answers each one. There are
four more ways into the study: by tag ([Tag index](risk/tag-index.md)), by service ([Components](components/index.md)),
by term ([Glossary](reference/glossary.md)) and by what is not known ([What is not
known](troubleshooting/what-is-not-known.md)). This page adds no finding of its own: every entry restates what the
linked section says, and the linked section is the reference.

## Scope

The portal is a source-level study of Kolla-Ansible `2023.1-eol` (`openstack/kolla-ansible`, tag `2023.1-eol`, commit
`4891a21`). All conclusions come from the 2023.1 implementation, not from older or newer releases ([Method and limits
of the study](reference/method-and-limits.md)).

| Component | Version |
|---|---|
| OpenStack release | 2023.1 (`openstack_release: "2023.1"`, `ansible/group_vars/all.yml:578`) |
| Kolla-Ansible | 16.x series, the 2023.1 series: tag `2023.1-eol`, commit `4891a21` |
| Kolla (images) | tag `2023.1-eol` of `openstack/kolla`, commit `de82941` |
| ansible-collection-kolla | tag `2023.1-eol` (pinned by `requirements.yml`: `unmaintained/2023.1`) |
| Ansible | ansible-core 2.14.18 (`tools/kolla-ansible:10-11` accepts 2.13 to 2.14) |

- **Source code only.** The study rests only on reading source code: kolla-ansible `2023.1-eol`, the kolla image
  repository `2023.1-eol`, ansible-collection-kolla `2023.1-eol` and the ansible-core 2.14.18 source. The only Ansible
  output used is its `--list-tags`/`--list-tasks` parse of the playbooks, which runs nothing against a host.
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code.
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].

The other limits are in [Limits of this study](reference/method-and-limits.md#limits-of-this-study).
