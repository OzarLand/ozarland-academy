---
template: home.html
title: Kolla-Ansible Academy
description: "Source-level study of Kolla-Ansible 20.x (OpenStack 2025.1, tag 2025.1-eom): what each tag really executes and what commands do to a running platform."
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

    Risk and impact: the 33 rated risks, what a tag really executes, and why a small change creates a large
    workload.

- **[I want to understand how a run works](concepts/index.md)**

    ---

    Concepts: repository architecture, deployment execution flow, compute scaling, and what the kolla images do at
    container start.

- **[I need the detailed evidence](reference/index.md)**

    ---

    Reference: findings, glossary, generated inventory, per-role fact sheets, Ansible listings, and the method and
    limits of the study.

</div>

Operator situations, from an incident to a failed VM deployment, are mapped to the pages to open first in [Start from a
situation](start/find-it-fast.md#start-from-a-situation).

## New in 2025.1

What changes for an operator with 2025.1, and what a cloud deployed by 2024.1 meets on its first 2025.1 run, each with
the section that gives the evidence. The study reads the code only: what a lab run has not confirmed is left for the
community to confirm, and feedback is welcome through an issue on the repository.

- **Only drifted containers restart.** Loop-notify is gone: the shared `service-check-containers` step notifies only the
  containers it found changed ([F1](reference/findings.md#f1), [Tags §2.4](risk/tags.md#24-loop-notify-is-gone-in-20251-code)).
- **A service tag no longer restarts HAProxy.** The frontend file is written and waits for `-t haproxy` or an untagged
  run ([F18](reference/findings.md#f18)).
- **`reconfigure` and `upgrade` cannot be batched.** They always run with `kolla_serial=0`; use `deploy -e
  kolla_serial=N` ([F19](reference/findings.md#f19)).
- **Restarts without an operator change on the first run.** The systemd unit template changed and, with Docker outside
  the Red Hat family, the default ulimits ([F16](reference/findings.md#f16)); classic RabbitMQ queues must be migrated
  first ([F17](reference/findings.md#f17)); with OVN, the chassis move to the Southbound relays
  ([R33](risk/risk-register.md#r33)). How to see them before the run: [Predict and inspect a run
  §2](operations/predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241).
- **New defaults and removals.** RabbitMQ 4.0, ProxySQL in front of MariaDB, the Octavia jobboard on Valkey or Redis;
  Swift is no longer deployed ([Swift](components/swift.md)). The CLI is now a Python program, with
  `migrate-container-engine` ([R31](risk/risk-register.md#r31)).

## Frequently used procedures

The operation pages that [Find it fast](start/find-it-fast.md) and [Ten things to know before a production
run](start/ten-things-to-know.md) point to most often:

- [Reconfigure a single service](operations/reconfigure-a-service.md) — what a single-service reconfigure such as
  `-t keystone` runs, and what the tag also touches
- [Reconfigure Nova](operations/reconfigure-nova.md) — what `-t nova reconfigure` runs on the controllers and on every
  compute
- [Write config first, apply in controlled batches](operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch, or a rolling `deploy -e kolla_serial=N`
- [Update container images](operations/update-container-images.md) — how `pull`, `deploy`, `reconfigure` and `upgrade`
  treat images
- [Add a compute node](operations/add-a-compute-node.md) — the three commands with `--limit`, and what
  `deploy --limit` touches on the other hosts

Every operation page is in the [Operations catalogue](operations/index.md#operations-catalogue), and the [Command quick
lookup by tag](operations/command-quick-lookup.md) has one row per command and tag.

## Before any production run

- [Pre-execution checklist](operations/pre-execution-checklist.md) — the eight checks to make before every production
  run, and what to add on the first 2025.1 run after 2024.1
- [Predict and inspect a run](operations/predict-a-run.md) — the commands that show what a run would target, render
  and restart
- [Ten things to know before a production run](start/ten-things-to-know.md) — ten points, most of them with the
  section that gives the evidence

## Recently updated

<div data-portal-recent="8" markdown>

Every change is in the
[commit history of the repository](https://github.com/OzarLand/ozarland-academy/commits/main/docs/day2/2025.1).

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
- `writes-config` — the command renders config and, apart from two narrow cases, restarts no container.
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

The portal is a source-level study of Kolla-Ansible `2025.1-eom` (`openstack/kolla-ansible`, tag `2025.1-eom`, commit
`7222f0f`). All conclusions come from the 2025.1 implementation, not from older or newer releases ([Method and limits
of the study](reference/method-and-limits.md)). The study of the previous release is the [2024.1
study](../2024.1/).

| Component | Version |
|---|---|
| OpenStack release | 2025.1 (`openstack_release: "2025.1"`, `group_vars/all.yml:795`) |
| Kolla-Ansible | 20.x series, the 2025.1 series: tag `2025.1-eom`, commit `7222f0f` |
| Kolla (images) | tag `2025.1-eom` of `openstack/kolla`, commit `c4b53a2` |
| ansible-collection-kolla | tag `2025.1-eom`, commit `09189c7` (`requirements.yml` pins `stable/2025.1`, `requirements.yml:5`) |
| Ansible | ansible-core 2.18.20 (`requirements.txt:14` accepts 2.17 to 2.18) |

- **Source code only.** The study rests only on reading source code: kolla-ansible `2025.1-eom`, the kolla image
  repository `2025.1-eom`, ansible-collection-kolla `2025.1-eom` and the ansible-core 2.18.20 source. The only Ansible
  output used is its `--list-tags`/`--list-tasks` parse of the playbooks, which runs nothing against a host.
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code.
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE]. The Podman paths were read in the code only, and ansible-core 2.17 was not read. These points are
  left for the community to confirm.

The other limits are in [Limits of this study](reference/method-and-limits.md#limits-of-this-study).
