---
template: home.html
title: Kolla-Ansible Academy
description: "Source-level study of Kolla-Ansible 10.x (OpenStack Ussuri, tag ussuri-eol): what each tag really executes and what commands do to a running platform."
tags: [reconfigure, deploy, tags, risk, evidence, unknowns]
---

# Kolla-Ansible Academy

<img src="assets/images/S3-opening.webp" width="1536" height="1024" alt="LUMO, a small book at hand, sits at a library table beside Ilyan, a grey-bearded librarian with glasses who reads a parchment covered in abstract marks.">

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

    Risk and impact: the 25 rated risks, what a tag really executes, and why a small change creates a large workload.

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
[commit history of the repository](https://github.com/OzarLand/ozarland-academy/commits/main/docs/day2/ussuri).

</div>

## How to read this portal

<img src="assets/images/S3-studies-shelves.webp" width="1536" height="1024" loading="lazy" alt="Ilyan and LUMO stand beside a long bookcase in which three sections are filled with books bound in different wood tones and two are still empty.">

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

<img src="assets/images/S3-lumo-pose.webp" width="280" height="280" loading="lazy" alt="LUMO in a navy cape holds an open book, with a compass, route pins and a small lantern on the satchel and belt.">

The portal is a source-level study of Kolla-Ansible `ussuri-eol` (`openstack/kolla-ansible`, tag `ussuri-eol`, HEAD
`8a94fe9`). All conclusions come from the Ussuri implementation, not from newer releases ([Method and limits of the
study](reference/method-and-limits.md)).

| Component | Version |
|---|---|
| OpenStack release | Ussuri (`openstack_release: "ussuri"`, `ansible/group_vars/all.yml:530`) |
| Kolla-Ansible | 10.x series, the Ussuri series: tag `ussuri-eol`, commit `8a94fe9`. The last numbered release tag of the series in `openstack/kolla-ansible` is `10.4.0`; `ussuri-eol` is a later commit |
| Kolla (images) | tag `ussuri-eol` of `openstack/kolla` |
| Ansible | 2.9.27 |

- **Source code only.** The study rests only on reading source code: kolla-ansible `ussuri-eol`, the kolla image
  repository `ussuri-eol`, and the Ansible 2.9.27 source (2.8.20 for comparison). The only Ansible output used is its
  `--list-tags`/`--list-tasks` parse of the playbooks, which runs nothing against a host.
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code.
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].

The other limits are in [Limits of this study](reference/method-and-limits.md#limits-of-this-study).
