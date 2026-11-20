---
title: Method and limits of the study
description: How the Kolla-Ansible 2023.1-eol sources were read, starting from the Ussuri study and re-checking every statement, and the limits of the study.
tags: [evidence, unknowns, images]
remember:
  - "The study rests only on reading source code: no runtime or lab result is used, from Ussuri or from 2023.1."
  - "Every statement was re-checked against the 2023.1 sources; nothing is carried over from Ussuri, from newer releases or from documentation the code does not confirm."
  - "There are no timings: no run is used, so no wall time is known; work can only be counted from the code."
  - "No container or VM behaviour is used as evidence: every statement about data-plane or VM impact is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
  - "The kolla image sources were read, not built or run: what the scripts do against real services and data is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
quiz:
  - q: "Was any run against a host used as evidence for the 2023.1 pages?"
    options: ["Yes: real-Docker lab experiments confirmed the restart behaviour", "No: the study rests only on reading source code"]
    answer: 1
    explain: "The only Ansible output used is the <code>--list-tags</code>/<code>--list-tasks</code> parse of the playbooks, which runs nothing against a host. No runtime or lab result is used, from Ussuri or from 2023.1."
    see: "limits-of-this-study"
  - q: "What does the study tell you about the impact of a command on running VMs and the data plane?"
    options: ["Nothing established: every such statement is <span class=\"ev ev-na\">NOT AVAILABLE</span>", "It is measured in the Ussuri lab runs, which carry over to 2023.1"]
    answer: 0
    explain: "No container or VM behaviour is used as evidence, so every statement about data-plane or VM impact is <span class=\"ev ev-na\">NOT AVAILABLE</span>. There are no timings either: work can only be counted from the code."
    see: "limits-of-this-study"
  - q: "How were statements from the earlier Ussuri study treated for 2023.1?"
    options: ["Kept as they were wherever the cited file still exists", "Kept when the cited lines were unchanged", "Every statement was re-checked against the 2023.1 sources; nothing is carried over from Ussuri"]
    answer: 2
    explain: "Each Ussuri citation was looked up in the 2023.1 sources by its cited text, and every statement was then re-read against those sources. Unmarked citations were re-read too, since the same lines do not prove the same behaviour."
    see: "method"
---

# Method and limits of the study

A source-level study of **Kolla-Ansible `2023.1-eol`** (`openstack/kolla-ansible`, tag `2023.1-eol`, 16.x series,
commit `4891a21`). It covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really executes, how
runs scale with the number of compute nodes, and what Kolla-Ansible commands do to a running production platform.

The pages were re-studied from the earlier study of `ussuri-eol`: every statement was re-checked against the 2023.1
sources, and nothing is carried over from Ussuri, from newer releases or from documentation that the code does not
confirm. Each conclusion is labelled with its evidence level: **[CODE]** or **[NOT AVAILABLE]** (see [Evidence
labels](../start/conventions.md#evidence-labels)).

> [!NOTE]
> **Key answers**
>
> - **Sources:** kolla-ansible, kolla and ansible-collection-kolla at `2023.1-eol`, and ansible-core 2.14.18
>   ([Sources](#sources)).
> - **How the 2023.1 pages were made:** each Ussuri `path:line` citation was looked up in the 2023.1 sources by its
>   cited text, and every statement was then re-read against those sources ([Method](#method)).
> - **Limits of the study:** source code only and no timings; every statement about data-plane or VM impact is
>   [NOT AVAILABLE]. No runtime or lab result is used, from Ussuri or from 2023.1 ([Limits of this
>   study](#limits-of-this-study)).

## Sources

| Source | Version |
|---|---|
| kolla-ansible | tag `2023.1-eol` (16.x series, commit `4891a21`); `openstack_release: "2023.1"` (`group_vars/all.yml:578`) |
| kolla (image repository) | tag `2023.1-eol` (commit `de82941`) |
| ansible-collection-kolla | tag `2023.1-eol`; kolla-ansible's `requirements.yml` pins the `unmaintained/2023.1` branch |
| ansible-core | 2.14.18. `tools/kolla-ansible:10-11` accepts 2.13 to 2.14; only 2.14.18 was read, so whether 2.13 behaves the same is [NOT AVAILABLE] |

The Ussuri sources (kolla-ansible and kolla `ussuri-eol`, Ansible 2.9.27) were read only to see what changed. No
statement about 2023.1 rests on them.

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration (Ussuri study) | Read `tools/kolla-ansible`, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the `kolla_docker`/`kolla_toolbox` modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full, plus the kolla image start path and one-shot containers |
| 2. Seeding the 2023.1 pages | The Ussuri pages were copied, and each Ussuri `path:line` citation was looked up in the 2023.1 sources by its cited text. Unchanged text (same lines, shifted lines or moved file) had its line numbers and path rewritten; changed, removed or ambiguous text was marked for a re-study by hand |
| 3. Re-study | Every marked citation was re-studied in the 2023.1 sources and its prose rewritten. Unmarked citations and statements without a citation (commands, counts, lists of tags, containers and hosts) were re-read too, since the same lines do not prove the same behaviour. The known structural changes were each checked in the code: `haproxy` → `loadbalancer` (+ `proxysql-config`, `hacluster`); `bootstrap-servers` → ansible-collection-kolla roles; containers under systemd units; `chrony` gone; `ovn` → `ovn-controller` + `ovn-db`; `elasticsearch` → `opensearch`; Ansible 2.9 → ansible-core 2.14. The container engine is Docker only in `ansible/` (`kolla_container_engine` defaults to `docker`, `group_vars/all.yml:92`) |
| 4. Kolla image sources | Re-read in kolla `2023.1-eol`: the base start path and the start scripts of the images listed in [Kolla images §1](../concepts/kolla-images.md#1-scope-and-method) |
| 5. Generated material | Regenerated from the 2023.1 tree, not edited by hand: [Generated inventory](generated-inventory.md) (`tools/extract_kolla_inventory.py`), the service cards of the [component pages](../components/index.md) (`tools/service_cards.py`) and the [Ansible listings](listings/index.md) (ansible-core 2.14.18) |
| 6. Dependency, performance and operational analysis | Re-done on 2023.1 from the role sources → [Component dependencies](../components/dependencies.md), [Compute scaling](../concepts/compute-scaling-and-performance.md), [Operations](../operations/index.md), [Risk register](../risk/risk-register.md). Risk IDs, finding IDs, question IDs and anchors were kept; an item that no longer holds in 2023.1 keeps its entry and says so, with the code |
| 7. Validation | ansible-core 2.14.18: `--list-tags`/`--list-tasks` listings of the real playbook ([Ansible listings](listings/index.md)); loop-notify, tag inheritance, `run_once` with `serial`, handler and loop semantics read in the ansible-core 2.14.18 source; the `kolla_docker` timeout handling read in the module source ([F3](findings.md#f3)) |

## Limits of this study

- **Source code only.** The study rests only on reading source code: kolla-ansible, kolla and
  ansible-collection-kolla `2023.1-eol`, and the ansible-core 2.14.18 source. The only Ansible output used is its
  `--list-tags`/`--list-tasks` parse of the playbooks ([Ansible listings](listings/index.md)), which runs nothing
  against a host. The semantics of `kolla_set_configs --check` are read from the kolla source ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- **No runtime or lab evidence, from either release.** The published Ussuri study used none either. Its Ansible
  listings were Ansible 2.9.27 output and do not carry over: they were regenerated with ansible-core 2.14.18 from the
  2023.1 tree, and the statements that cite them ([F7](findings.md#f7), [Tags
  §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) were re-read against the new files. Earlier
  drafts of the Ussuri study held real-Docker lab experiments and lab scaling runs; they were removed before the Ussuri
  pages were published, and nothing from them is used here. The subjects they touched stay code-only or
  [NOT AVAILABLE] in 2023.1:
  - signal delivery to services behind a shell wrapper that does not `exec` them: [NOT AVAILABLE]
    ([R24](../risk/risk-register.md#r24), [Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1));
  - `kolla_set_configs` and `kolla_docker` behaviour (check exit codes, restart and recreate): code-only
    ([F14](findings.md#f14),
    [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes),
    [F3](findings.md#f3));
  - libvirt/QEMU and Open vSwitch behaviour across container restarts: [NOT AVAILABLE]
    ([Q1](../troubleshooting/open-questions.md#q1), [Q2](../troubleshooting/open-questions.md#q2),
    [Q3](../troubleshooting/open-questions.md#q3));
  - task-result counts per compute, restart timings and wall time at 3, 10 and 30 computes: [NOT AVAILABLE]; only work
    counted from the code is given ([Compute scaling](../concepts/compute-scaling-and-performance.md),
    [Q7](../troubleshooting/open-questions.md#q7));
  - `--limit` fact gathering and `run_once` repeats with `serial`: code-only ([F9](findings.md#f9),
    [F10](findings.md#f10)).
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code ([Compute
  scaling](../concepts/compute-scaling-and-performance.md)).
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].
- **The depth of reading varies.** The core services are traced in the pages of the study other than the fact sheets;
  the other roles are covered by the [fact sheets](factsheets/index.md) only.
- **Only one ansible-core version was read.** Kolla-Ansible 2023.1 also accepts ansible-core 2.13
  (`tools/kolla-ansible:10-11`); its behaviour is [NOT AVAILABLE].
- **The kolla image sources were read, not built or run.** From the kolla `2023.1-eol` repository: the base start path
  (`docker/base`: `Dockerfile.j2`, `start.sh`, `set_configs.py`, `copy_cacerts.sh`, `httpd_setup.sh`, `sudoers`,
  healthcheck scripts) and the start scripts of the images listed in [Kolla images](../concepts/kolla-images.md) (Nova,
  Neutron, Open vSwitch, OVN, Keystone, Glance, Placement, Cinder, Heat, Horizon, Barbican, Octavia, Manila, Swift,
  MariaDB, RabbitMQ, memcached, HAProxy, keepalived incl. `check_alive.sh`, fluentd, cron, kolla-toolbox, iscsid,
  tgtd; the Ussuri chrony image does not exist in 2023.1). Of the other images only the `ironic-api` bootstrap branch
  and the `bifrost-deploy` `ENTRYPOINT`/`CMD` were read, and every Dockerfile was searched for `HEALTHCHECK` and for
  `ENTRYPOINT`/`CMD` overrides. What the scripts do against real services and data is [NOT AVAILABLE].

## Related

- [Conventions and evidence labels](../start/conventions.md) — the definition of [CODE] and [NOT AVAILABLE]
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Open questions](../troubleshooting/open-questions.md) — the open questions
  [Q1–Q14](../troubleshooting/open-questions.md#q1)
- [Technical findings](findings.md) — the fifteen headline findings, each with its evidence and its 2023.1 status
- [Per-role fact sheets](factsheets/index.md) — the five fact sheets and how they were checked
- [Ansible listings](listings/index.md) — the `--list-tags` and `--list-tasks` listings used in the validation phase
