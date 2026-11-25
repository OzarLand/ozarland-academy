---
title: Method and limits of the study
description: How the Kolla-Ansible 2025.1-eom sources were read, starting from the 2024.1 study and re-checking every statement, and the limits of the study.
tags: [evidence, unknowns, images]
remember:
  - "The study rests only on reading source code: no runtime or lab result is used, from 2024.1 or from 2025.1."
  - "Every statement was re-checked against the 2025.1 sources; nothing is carried over from 2024.1, from 2024.2, from newer releases or from documentation the code does not confirm."
  - "The study goes straight from 2024.1 to 2025.1, two SLURP releases; 2024.2 was not studied."
  - "There are no timings: no run is used, so no wall time is known; work can only be counted from the code."
  - "Only ansible-core 2.18.20 was read: Kolla-Ansible 2025.1 also accepts 2.17, whose behaviour is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
quiz:
  - q: "Was any run against a host used as evidence for the 2025.1 pages?"
    options: ["Yes: the Ansible listings were produced by running the playbooks against a lab", "No: the study rests only on reading source code"]
    answer: 1
    explain: "The only Ansible output used is the ansible-core 2.18.20 <code>--list-tags</code>/<code>--list-tasks</code> parse of the playbooks, which runs nothing against a host. No runtime or lab result is used, from 2024.1 or from 2025.1."
    see: "limits-of-this-study"
  - q: "Does <code>kolla-ansible upgrade -e kolla_serial=30%</code> upgrade the hosts in batches in 2025.1?"
    options: ["Yes: the user's <code>-e</code> always wins", "No: the CLI adds <code>-e kolla_serial=0</code> after the user's options, and ansible-core keeps the last value"]
    answer: 1
    explain: "The CLI puts its own extra vars after the user's <code>-e</code> options, and <code>upgrade</code> always sets <code>kolla_serial=0</code>. ansible-core merges the <code>-e</code> options in order, a later value replacing an earlier one, so the plays see 0 <span class=\"ev ev-code\">CODE</span>. No run has confirmed it."
    see: "limits-of-this-study"
  - q: "How were statements from the 2024.1 study treated for 2025.1?"
    options: ["Kept as they were wherever the cited lines are unchanged", "Kept when the cited file still exists", "Every 2024.1 citation was looked up in the 2025.1 sources and every statement re-read; nothing is carried over"]
    answer: 2
    explain: "The 2024.1 pages give only the structure and the questions. Each 2024.1 citation was looked up in the 2025.1 sources and every statement re-read there, since the same lines do not prove the same behaviour."
    see: "method"
---

# Method and limits of the study

A source-level study of **Kolla-Ansible `2025.1-eom`** (`openstack/kolla-ansible`, tag `2025.1-eom`, 20.x series,
commit `7222f0f`). It covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really executes, how
runs scale with the number of compute nodes, and what Kolla-Ansible commands do to a running production platform.

The pages were re-studied from the earlier study of `2024.1-eom`: every 2024.1 citation was looked up in the 2025.1
sources and every statement was re-read there. Nothing is carried over from 2024.1, from 2024.2, from newer releases or
from documentation that the code does not confirm. Each conclusion is labelled with its evidence level: **[CODE]** or
**[NOT AVAILABLE]** (see [Evidence labels](../start/conventions.md#evidence-labels)).

> [!NOTE]
> **Key answers**
>
> - **Sources:** kolla-ansible, kolla and ansible-collection-kolla at `2025.1-eom`, and ansible-core 2.18.20
>   ([Sources](#sources)).
> - **2024.2 was skipped:** 2024.1 and 2025.1 are both SLURP releases, so an upgrade may skip 2024.2, and the study
>   does the same. The changes of 2024.2 are part of what changed between the two studied trees ([Method](#method)).
> - **How the 2025.1 pages were made:** each 2024.1 page gave the structure and the questions; each of its
>   `path:line` citations was looked up in the 2025.1 sources and every statement was re-read there, guided by a map of
>   the changes between the two trees ([Method](#method)).
> - **Limits of the study:** source code only and no timings; every statement about data-plane or VM impact is
>   [NOT AVAILABLE]. Ten points that only a run can settle are listed, among them batching with `kolla_serial` under
>   the new CLI ([Limits of this study](#limits-of-this-study)).

## Sources

| Source | Version |
|---|---|
| kolla-ansible | tag `2025.1-eom` (20.x series, commit `7222f0f`); `openstack_release: "2025.1"` (`group_vars/all.yml:795`) |
| kolla (image repository) | tag `2025.1-eom` (commit `c4b53a2`) |
| ansible-collection-kolla | tag `2025.1-eom` (commit `09189c7`); kolla-ansible's `requirements.yml` pins the `stable/2025.1` branch |
| ansible-core | 2.18.20. kolla-ansible requires `ansible-core>=2.17,<2.19` (`requirements.txt:14`); only 2.18.20 was read, so whether 2.17 behaves the same is [NOT AVAILABLE] |

Changed from 2024.1: the 2024.1 study read the `2024.1-eom` tags (kolla-ansible commit `890396f`, kolla `ed7a36a`,
collection `82a0f5c`) and ansible-core 2.16.20. Those sources, and ansible-core 2.16.20, were read only to see what
changed, mostly with `git diff` of the two tags. No statement about 2025.1 rests on them.

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration (earlier studies) | The Ussuri study read the CLI, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the container and toolbox modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full, plus the kolla image start path and one-shot containers; the 2023.1 and 2024.1 studies re-read them in their own tags. These phases set the structure and the questions of the pages, not their answers |
| 2. Change map | Before the pages were written, the two tags were diffed in the parts of the code that decide what Day-2 commands do (719 files changed under `ansible/`). The result is a working map of the cross-cutting changes 2024.1 → 2025.1 (`research/2025.1/change-map.md`, items X1–X20, each with 2025.1 citations), of the 2024.1 pages each change touches, and of the points that need a run. It is used as a map only: every statement of a page is re-verified in the 2025.1 code |
| 3. Re-study | Each page starts from its 2024.1 page for its structure and its questions, never for its answers. Every 2024.1 `path:line` citation was looked up in the 2025.1 sources and every statement was re-read there, with its own 2025.1 citation; statements without a citation (commands, counts, lists of tags, containers and hosts) were re-read too, since the same lines do not prove the same behaviour. A statement that no longer holds says so, with the code; one that could not be re-verified was dropped or labelled [NOT AVAILABLE]. The main structural changes were each checked in the code, for example: the CLI is now a Python program built on `cliff` (`setup.cfg:43-77`, `kolla_ansible/cli/commands.py`), so the 138 citations of `tools/kolla-ansible` in the 2024.1 pages have no target; `ANSIBLE_SERIAL` and `--forks` are gone (`kolla_ansible/cli/commands.py:20-22`, `kolla_ansible/ansible.py:30-125`); the config step of almost every role no longer notifies handlers, and one shared role decides restarts (`roles/service-check-containers/tasks/main.yml`); ProxySQL is the default database load balancer (`group_vars/all.yml:958`); classic mirrored RabbitMQ queues are gone (no `om_enable_rabbitmq_high_availability` in `group_vars/all.yml`); the `swift` role is removed and `valkey` added (`site.yml:399-411`) |
| 4. Kolla image sources | Re-read in kolla `2025.1-eom`: the base start path and the start scripts of the images listed in [Kolla images §1](../concepts/kolla-images.md#1-scope-and-method), with `git diff` of `docker/base` against `2024.1-eom` (`set_configs.py` +90 lines: `--check` now also compares the running command and the saved defaults state) |
| 5. Generated material | Regenerated from the 2025.1 tree, not edited by hand: [Generated inventory](generated-inventory.md) (`tools/extract_kolla_inventory.py`; 71 plays, 161 containers), the [Ansible listings](listings/index.md) (ansible-core 2.18.20) and the service cards of the component pages (`tools/service_cards.py`, run with the `multinode` inventory parsed by ansible-core 2.18.20). The 2024.1 listings, ansible-core 2.16.20 output, do not carry over |
| 6. Dependency, performance and operational analysis | Re-done on 2025.1 from the role sources. Risk IDs, finding IDs, question IDs and anchors are kept; an item that no longer holds in 2025.1 keeps its entry and says so, with the code |
| 7. Validation | ansible-core 2.18.20: `--list-tags`/`--list-tasks` listings of the unmodified playbooks ([Ansible listings](listings/index.md)); play and batch semantics read in the ansible-core 2.18.20 source, for example that `max_fail_percentage` counts the failures of the current batch only (`lib/ansible/executor/playbook_executor.py:179-188`, `lib/ansible/executor/task_queue_manager.py:328-334`). Each page is checked by a citation checker that flags line ranges beyond the end of the cited file and citations whose text is identical to the 2024.1 page while the cited lines changed; each flagged citation was corrected or confirmed against the 2025.1 file |

## Limits of this study

- **Source code only.** The study rests only on reading source code: kolla-ansible, kolla and
  ansible-collection-kolla `2025.1-eom`, and the ansible-core 2.18.20 source. The only Ansible output used is its
  `--list-tags`/`--list-tasks` parse of the playbooks ([Ansible listings](listings/index.md)), produced with the
  `multinode` example inventory, Kolla-Ansible 2025.1 installed in a virtual environment and ansible-collection-kolla
  `2025.1-eom` on the collections path; it runs nothing against a host. The semantics of `kolla_set_configs --check`
  are read from the kolla source ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- **No runtime or lab evidence, from either release.** The 2024.1 study used none either. The subjects that only a run
  could settle stay code-only or [NOT AVAILABLE] in 2025.1:
  - whether `upgrade` or `reconfigure` given `-e kolla_serial=N` really runs unbatched: the CLI adds
    `-e kolla_serial=0` after the user's options (`kolla_ansible/ansible.py:261-266`,
    `kolla_ansible/cli/commands.py:136,278`) and ansible-core keeps the last value (ansible-core 2.18.20
    `lib/ansible/utils/vars.py:94-105, :198-224`), so the code says 0 [CODE]; no run has confirmed it
    ([Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order));
  - which containers restart at the first `deploy` or `reconfigure` after an upgrade from 2024.1, when the unit file
    template (`module_utils/kolla_systemd_worker.py:27`) and `kolla_set_configs --check` (kolla
    `docker/base/set_configs.py:580-643`) both changed: code-only ([F3](findings.md#f3),
    [F14](findings.md#f14));
  - the switch of the database load balancer from HAProxy to ProxySQL on a running platform
    (`group_vars/all.yml:554,958`): [NOT AVAILABLE];
  - signal delivery to services behind a shell wrapper that does not `exec` them: [NOT AVAILABLE]
    ([R24](../risk/risk-register.md#r24), [Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1));
  - libvirt/QEMU and Open vSwitch behaviour across container restarts: [NOT AVAILABLE]
    ([Q1](../troubleshooting/open-questions.md#q1), [Q2](../troubleshooting/open-questions.md#q2),
    [Q3](../troubleshooting/open-questions.md#q3));
  - task-result counts per compute, restart timings and wall time at any number of computes: [NOT AVAILABLE]; only
    work counted from the code is given ([Compute scaling](../concepts/compute-scaling-and-performance.md),
    [Q7](../troubleshooting/open-questions.md#q7));
  - `--limit` fact gathering and `run_once` repeats with `serial`: code-only ([F9](findings.md#f9),
    [F10](findings.md#f10)).
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code ([Compute
  scaling](../concepts/compute-scaling-and-performance.md)).
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].
- **The Podman paths were read in the code only.** `kolla_container_engine: podman` selects the Podman worker
  (`library/kolla_container.py:411-416`). That worker (changed by 232 lines since 2024.1), the new
  `migrate-container-engine` playbook and the Podman branches of the roles were read; the Podman Python client, Podman
  itself and systemd were not, and no Podman host was used. What they do on a host is [NOT AVAILABLE].
- **The depth of reading varies.** The core services are traced in the pages of the study other than the fact sheets;
  the other roles are covered by the [fact sheets](factsheets/index.md) only.
- **Only one ansible-core version was read.** Kolla-Ansible 2025.1 also accepts ansible-core 2.17
  (`requirements.txt:14`); its behaviour is [NOT AVAILABLE]. ansible-core 2.16.20 was put on disk only to locate the
  2024.1 citations in 2.18.20; no statement rests on it.
- **The galaxy collections were not on disk.** Only ansible-collection-kolla (`openstack.kolla`) was read and put on
  the collections path. `kolla-ansible install-deps` installs both `requirements.yml` and `requirements-core.yml`
  (`kolla_ansible/ansible.py:307-318`); the latter pins galaxy collections such as `community.docker <5` and
  `containers.podman <2` (`requirements-core.yml:18-23`). Their modules were not read, so what they do is
  [NOT AVAILABLE].
- **The kolla image sources were read, not built or run.** From the kolla `2025.1-eom` repository: the base start path
  (`docker/base`) and the start scripts of the images listed in [Kolla images](../concepts/kolla-images.md). There is
  no Swift image any more (no `docker/swift` directory) and still no chrony image. What the scripts do against real
  services and data is [NOT AVAILABLE].

## Related

- [Conventions and evidence labels](../start/conventions.md) — the definition of [CODE] and [NOT AVAILABLE]
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Open questions](../troubleshooting/open-questions.md) — the open questions
- [Technical findings](findings.md) — the headline findings, each with its evidence and its 2025.1 status
- [Per-role fact sheets](factsheets/index.md) — the five fact sheets A–E and how they were checked
- [Ansible listings](listings/index.md) — the `--list-tags` and `--list-tasks` listings used in the validation phase
- [Generated inventory](generated-inventory.md) — the plays and containers generated from the 2025.1 tree
