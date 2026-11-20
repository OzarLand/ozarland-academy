---
title: Method and limits of the study
description: How the Kolla-Ansible 2024.1-eom sources were read, starting from the 2023.1 study and re-checking every statement, and the limits of the study.
tags: [evidence, unknowns, images]
remember:
  - "The study rests only on reading source code: no runtime or lab result is used, from 2023.1 or from 2024.1."
  - "Every statement was re-checked against the 2024.1 sources; nothing is carried over from 2023.1, from newer releases or from documentation the code does not confirm."
  - "There are no timings: no run is used, so no wall time is known; work can only be counted from the code."
  - "The Podman paths that are new in 2024.1 were read in the code only; how Podman and systemd behave on a host is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
  - "Only ansible-core 2.16.20 was read: Kolla-Ansible 2024.1 also accepts 2.15, whose behaviour is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
quiz:
  - q: "Was any run against a host used as evidence for the 2024.1 pages?"
    options: ["Yes: the Ansible listings were produced by running the playbooks against a lab", "No: the study rests only on reading source code"]
    answer: 1
    explain: "The only Ansible output used is the ansible-core 2.16.20 <code>--list-tags</code>/<code>--list-tasks</code> parse of the playbooks, which runs nothing against a host. No runtime or lab result is used, from 2023.1 or from 2024.1."
    see: "limits-of-this-study"
  - q: "What does the study tell you about how a deployment with <code>kolla_container_engine: podman</code> behaves on a host?"
    options: ["Only what the code of the Podman worker and the roles says; behaviour on a host is <span class=\"ev ev-na\">NOT AVAILABLE</span>", "It is the same as Docker, since both workers share the drift test"]
    answer: 0
    explain: "The Podman paths were read in Kolla-Ansible's own code only. The Podman Python client and the <code>containers.podman</code> collection were not on disk, and nothing was run, so what Podman and systemd do on a host is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "limits-of-this-study"
  - q: "How were statements from the 2023.1 study treated for 2024.1?"
    options: ["Kept as they were wherever the cited lines are unchanged", "Kept when the cited file still exists", "Every 2023.1 citation was looked up in the 2024.1 sources and every statement re-read; nothing is carried over"]
    answer: 2
    explain: "The 2023.1 pages give only the structure and the questions. Each 2023.1 citation was looked up in the 2024.1 sources and every statement re-read there, since the same lines do not prove the same behaviour."
    see: "method"
---

# Method and limits of the study

A source-level study of **Kolla-Ansible `2024.1-eom`** (`openstack/kolla-ansible`, tag `2024.1-eom`, 18.x series,
commit `890396f`). It covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really executes, how
runs scale with the number of compute nodes, and what Kolla-Ansible commands do to a running production platform.

The pages were re-studied from the earlier study of `2023.1-eol`: every 2023.1 citation was looked up in the 2024.1
sources and every statement was re-read there. Nothing is carried over from 2023.1, from newer releases or from
documentation that the code does not confirm. Each conclusion is labelled with its evidence level: **[CODE]** or
**[NOT AVAILABLE]** (see [Evidence labels](../start/conventions.md#evidence-labels)).

> [!NOTE]
> **Key answers**
>
> - **Sources:** kolla-ansible, kolla and ansible-collection-kolla at `2024.1-eom`, and ansible-core 2.16.20
>   ([Sources](#sources)).
> - **How the 2024.1 pages were made:** each 2023.1 page gave the structure and the questions; each of its
>   `path:line` citations was looked up in the 2024.1 sources and every statement was re-read there, guided by a map of
>   the changes between the two trees ([Method](#method)).
> - **Limits of the study:** source code only and no timings; every statement about data-plane or VM impact is
>   [NOT AVAILABLE]. The Podman paths new in 2024.1 were read in the code only, and ansible-core 2.15 was not read
>   ([Limits of this study](#limits-of-this-study)).

## Sources

| Source | Version |
|---|---|
| kolla-ansible | tag `2024.1-eom` (18.x series, commit `890396f`); `openstack_release: "2024.1"` (`group_vars/all.yml:679`) |
| kolla (image repository) | tag `2024.1-eom` (commit `ed7a36a`) |
| ansible-collection-kolla | tag `2024.1-eom` (commit `82a0f5c`); kolla-ansible's `requirements.yml:5` pins the `stable/2024.1` branch |
| ansible-core | 2.16.20. `tools/kolla-ansible:10-11` accepts 2.15 to 2.16; only 2.16.20 was read, so whether 2.15 behaves the same is [NOT AVAILABLE] |

Changed from 2023.1: the 2023.1 study read the `2023.1-eol` tags (kolla-ansible commit `4891a21`, kolla `de82941`,
collection pinned to `unmaintained/2023.1`) and ansible-core 2.14.18. The 2023.1 sources (kolla-ansible, kolla and
ansible-collection-kolla `2023.1-eol`) were read only to see what changed, mostly with `diff -ru` of the two trees. No
statement about 2024.1 rests on them. ansible-core 2.14.18 was not on disk for this study, so no ansible-core diff
between the two releases was made.

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration (earlier studies) | The Ussuri study read `tools/kolla-ansible`, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the container and toolbox modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full, plus the kolla image start path and one-shot containers; the 2023.1 study re-read them in `2023.1-eol`. These phases set the structure and the questions of the pages, not their answers |
| 2. Change map | Before the pages were written, the two trees were read and diffed in the parts of the code that decide what Day-2 commands do. The result is a working map of the cross-cutting changes 2023.1 → 2024.1 (`research/2024.1/change-map.md`, items X1–X18, each with 2024.1 citations) and of the 2023.1 pages each change touches. It is used as a map only: every statement of a page is re-verified in the 2024.1 code |
| 3. Re-study | Each page starts from its 2023.1 page for its structure and its questions, never for its answers. Every 2023.1 `path:line` citation was looked up in the 2024.1 sources and every statement was re-read there, with its own 2024.1 citation; statements without a citation (commands, counts, lists of tags, containers and hosts) were re-read too, since the same lines do not prove the same behaviour. A statement that no longer holds says so, with the code; one that could not be re-verified was dropped or labelled [NOT AVAILABLE]. The main structural changes were each checked in the code, for example: `kolla_docker` → `kolla_container`, which loads a Docker or a Podman worker after `container_engine` (`library/kolla_container.py:410-420`), fed from `kolla_container_engine` (`group_vars/all.yml:92,153`), so the 2023.1 statement "Docker only" no longer holds; a new systemd unit template (`module_utils/kolla_systemd_worker.py:20-39`); `max_fail_percentage` on every play and no `serial` on the etcd play (`site.yml:470-482`); RabbitMQ quorum queues on by default (`group_vars/all.yml:268`); removed services such as `murano`, `sahara` and `monasca` (no such directories under `ansible/roles/`); ansible-core 2.14 → 2.16 |
| 4. Kolla image sources | Re-read in kolla `2024.1-eom`: the base start path and the start scripts of the images listed in [Kolla images §1](../concepts/kolla-images.md#1-scope-and-method), with `diff -ru` of `docker/base` against `2023.1-eol` |
| 5. Generated material | Regenerated from the 2024.1 tree, not edited by hand: [Generated inventory](generated-inventory.md) (`tools/extract_kolla_inventory.py`; 71 plays, 159 containers), the [Ansible listings](listings/index.md) (ansible-core 2.16.20) and the service cards of the component pages (`tools/service_cards.py`, run with the `multinode` inventory parsed by ansible-core 2.16.20: 22 cards in 20 pages). The 2023.1 listings, ansible-core 2.14.18 output, do not carry over |
| 6. Dependency, performance and operational analysis | Re-done on 2024.1 from the role sources. Risk IDs, finding IDs, question IDs and anchors are kept; an item that no longer holds in 2024.1 keeps its entry and says so, with the code |
| 7. Validation | ansible-core 2.16.20: `--list-tags`/`--list-tasks` listings of the unmodified playbooks ([Ansible listings](listings/index.md)); play and batch semantics read in the ansible-core 2.16.20 source, for example that `max_fail_percentage` counts the failures of the current batch only (`lib/ansible/executor/playbook_executor.py:184-190`, `lib/ansible/executor/task_queue_manager.py:330-338`). Each page is checked by a citation checker that flags line ranges beyond the end of the cited file and citations whose text is identical to the 2023.1 page while the cited lines changed; each flagged citation was corrected or confirmed against the 2024.1 file |

## Limits of this study

- **Source code only.** The study rests only on reading source code: kolla-ansible, kolla and
  ansible-collection-kolla `2024.1-eom`, and the ansible-core 2.16.20 source. The only Ansible output used is its
  `--list-tags`/`--list-tasks` parse of the playbooks ([Ansible listings](listings/index.md)), produced with the
  `multinode` example inventory, Kolla-Ansible 2024.1 installed in a virtual environment and ansible-collection-kolla
  `2024.1-eom` on the collections path; it runs nothing against a host. The semantics of `kolla_set_configs --check`
  are read from the kolla source ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- **No runtime or lab evidence, from either release.** The 2023.1 study used none either. Its Ansible listings were
  ansible-core 2.14.18 output and do not carry over: they were regenerated with ansible-core 2.16.20 from the 2024.1
  tree. The subjects that only a run could settle stay code-only or [NOT AVAILABLE] in 2024.1:
  - signal delivery to services behind a shell wrapper that does not `exec` them: [NOT AVAILABLE]
    ([R24](../risk/risk-register.md#r24), [Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1));
  - `kolla_set_configs` and `kolla_container` behaviour (check exit codes, restart and recreate): code-only
    ([F14](findings.md#f14),
    [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes),
    [F3](findings.md#f3));
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
- **The Podman paths were read in the code only.** New in 2024.1, `kolla_container_engine: podman` selects the Podman
  worker (`library/kolla_container.py:415-420`), which talks to the Podman socket through the Podman Python client
  (`module_utils/kolla_podman_worker.py:21,73`). That worker and the Podman branches of the roles were read; the Podman
  Python client, Podman itself and systemd were not, and no Podman host was used. What they do on a host is
  [NOT AVAILABLE].
- **The depth of reading varies.** The core services are traced in the pages of the study other than the fact sheets;
  the other roles are covered by the [fact sheets](factsheets/index.md) only.
- **Only one ansible-core version was read.** Kolla-Ansible 2024.1 also accepts ansible-core 2.15
  (`tools/kolla-ansible:10-11`); its behaviour is [NOT AVAILABLE]. Nothing can be said from code about what changed in
  ansible-core itself between 2.14 and 2.16, since 2.14.18 was not on disk.
- **The galaxy collections were not on disk.** Only ansible-collection-kolla (`openstack.kolla`) was read and put on
  the collections path. When the `ansible` package is not installed, `kolla-ansible install-deps` also installs
  `requirements-core.yml` (`tools/kolla-ansible:131-138`), which pins galaxy collections such as `community.docker <4`
  and `containers.podman <2` (`requirements-core.yml:18-23`). Their modules were not read, so what they do is
  [NOT AVAILABLE].
- **The kolla image sources were read, not built or run.** From the kolla `2024.1-eom` repository: the base start path
  (`docker/base`: `Dockerfile.j2`, `start.sh`, `set_configs.py`, `copy_cacerts.sh`, `httpd_setup.sh`, `sudoers`,
  healthcheck scripts) and the start scripts of the images listed in [Kolla images](../concepts/kolla-images.md) (Nova,
  Neutron, Open vSwitch, OVN, Keystone, Glance, Placement, Cinder, Heat, Horizon, Barbican, Octavia, Manila, Swift,
  MariaDB, RabbitMQ, memcached, HAProxy, keepalived incl. `check_alive.sh`, fluentd, cron, kolla-toolbox, iscsid,
  tgtd; there is still no chrony image). Of the other images only the `ironic-api` bootstrap branch and the
  `bifrost-deploy` `ENTRYPOINT`/`CMD` were read, and every Dockerfile was searched for `HEALTHCHECK` and for
  `ENTRYPOINT`/`CMD` overrides. What the scripts do against real services and data is [NOT AVAILABLE].

## Related

- [Conventions and evidence labels](../start/conventions.md) — the definition of [CODE] and [NOT AVAILABLE]
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Open questions](../troubleshooting/open-questions.md) — the open questions Q1–Q21 (Q15–Q21 new in 2024.1)
- [Technical findings](findings.md) — the seventeen headline findings F1–F17 (F16 and F17 new in 2024.1), each with its
  evidence and its 2024.1 status
- [Per-role fact sheets](factsheets/index.md) — the five fact sheets A–E and how they were checked
- [Ansible listings](listings/index.md) — the `--list-tags` and `--list-tasks` listings used in the validation phase
- [Generated inventory](generated-inventory.md) — the plays and containers generated from the 2024.1 tree
