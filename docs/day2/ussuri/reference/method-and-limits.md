---
title: Method and limits of the study
description: How the Kolla-Ansible ussuri-eol sources were read, in six phases, and the limits of a study that rests on source code only.
tags: [evidence, unknowns, images]
remember:
  - "The study rests only on reading source code: kolla-ansible <code>ussuri-eol</code>, the kolla image repository <code>ussuri-eol</code> and the Ansible 2.9.27 source."
  - "All conclusions come from the Ussuri implementation, not from newer releases."
  - "There are no timings: no run is used, so no wall time is known; work can only be counted from the code."
  - "No container or VM behaviour is used as evidence: every statement about data-plane or VM impact is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
  - "The kolla image sources were read, not built or run: what the scripts do against real services and data is not available. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
quiz:
  - q: "Does the Ussuri study use any run against a host as evidence?"
    options: ["Yes: the <code>--list-tasks</code> listings ran the playbook against the hosts", "No: the only Ansible output used is the <code>--list-tags</code>/<code>--list-tasks</code> parse of the playbooks, which runs nothing against a host"]
    answer: 1
    explain: "The study rests only on reading source code: kolla-ansible <code>ussuri-eol</code>, the kolla image repository <code>ussuri-eol</code>, and the Ansible 2.9.27 source."
    see: "limits-of-this-study"
  - q: "Can you take restart or deploy wall times from this study?"
    options: ["No: no run is used, so no wall time is known; work can only be counted from the code", "Yes, from the performance analysis phase"]
    answer: 0
    explain: "There are no timings. The performance analysis read per-host task chains from the role sources and the <code>--list-tasks</code> listing; it ran nothing."
    see: "limits-of-this-study"
  - q: "Were the kolla images built and run to see what their start scripts do?"
    options: ["Yes, each image was built once for validation", "Only the Nova and Neutron images", "No: the kolla image sources were read, not built or run"]
    answer: 2
    explain: "The base start path and the start scripts of the listed images were read from the kolla <code>ussuri-eol</code> repository. What the scripts do against real services and data is <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "limits-of-this-study"
---

# Method and limits of the study

A source-level study of **Kolla-Ansible `ussuri-eol`** (`openstack/kolla-ansible`, tag `ussuri-eol`, HEAD `8a94fe9`). It
covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really executes, how runs scale with the
number of compute nodes, and what Kolla-Ansible commands do to a running production platform.

All conclusions come from the Ussuri implementation, not from newer releases. Each one is labelled with its evidence
level: **[CODE]** or **[NOT AVAILABLE]** (see [Evidence labels](../start/conventions.md#evidence-labels)).

> [!NOTE]
> **Key answers**
>
> - **Limits of the study:** source code only and no timings; every statement about data-plane or VM impact is
>   [NOT AVAILABLE] ([Limits of this study](#limits-of-this-study)).

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration | Cloned `ussuri-eol`; read `tools/kolla-ansible`, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the `kolla_docker`/`kolla_toolbox` modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full. Also read the kolla image repository (`ussuri-eol`) for the image start path and the one-shot containers ([Kolla images](../concepts/kolla-images.md)) |
| 2. Static analysis | Generated tables of all plays, containers, roles and handlers (`tools/extract_kolla_inventory.py`). Five parallel source-reading passes produced the fact sheets, which were then spot-checked |
| 3. Dependency mapping | Template references, transport URLs and group loops → [Component dependencies](../components/dependencies.md) |
| 4. Performance analysis | Per-host task chains read from the role sources and the `--list-tasks` listing → [Compute scaling](../concepts/compute-scaling-and-performance.md) |
| 5. Operational analysis | Day-2 scenarios traced through the role sources → [Operations](../operations/index.md), [Risk register](../risk/risk-register.md) |
| 6. Validation | Ansible 2.9.27 (the supported version): `--list-tags`/`--list-tasks` listings of the real playbook ([Ansible listings](listings/index.md)); loop-notify and tag inheritance read in the Ansible 2.9.27 source; the `kolla_docker` timeout override read in the module source |

## Limits of this study

- **Source code only.** The study rests only on reading source code: kolla-ansible `ussuri-eol`, the kolla image
  repository `ussuri-eol`, and the Ansible 2.9.27 source (2.8.20 for comparison). The only Ansible output used is its
  `--list-tags`/`--list-tasks` parse of the playbooks ([Ansible listings](listings/index.md)), which runs nothing
  against a host. The semantics of `kolla_set_configs --check` are read from the kolla source ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code ([Compute
  scaling](../concepts/compute-scaling-and-performance.md)).
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].
- **The depth of reading varies.** The core services are traced in the pages of the study other than the fact sheets;
  the other roles are covered by the [fact sheets](factsheets/index.md) only.
- **The kolla image sources were read, not built or run.** From the kolla `ussuri-eol` repository: the base start path
  (`docker/base`: `Dockerfile.j2`, `start.sh`, `set_configs.py`, `copy_cacerts.sh`, `httpd_setup.sh`, `sudoers`,
  healthcheck scripts) and the start scripts of the images listed in [Kolla images](../concepts/kolla-images.md) (Nova,
  Neutron, Open vSwitch, OVN, Keystone, Glance, Placement, Cinder, Heat, Horizon, Barbican, Octavia, Manila, Swift,
  MariaDB, RabbitMQ, memcached, HAProxy, keepalived incl. `check_alive.sh`, fluentd, cron, kolla-toolbox, chrony,
  iscsid, tgtd). Of the other images only the `ironic-api` bootstrap branch and the `bifrost-deploy` `ENTRYPOINT`/`CMD`
  were read, and every Dockerfile was searched for `HEALTHCHECK` and for `ENTRYPOINT`/`CMD` overrides. What the scripts
  do against real services and data is [NOT AVAILABLE].

## Related

- [Conventions and evidence labels](../start/conventions.md) — the definition of [CODE] and [NOT AVAILABLE]
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Open questions](../troubleshooting/open-questions.md) — the open questions
  [Q1–Q14](../troubleshooting/open-questions.md#q1)
- [Technical findings](findings.md) — the fifteen headline findings, each with its evidence
- [Per-role fact sheets](factsheets/index.md) — the five fact sheets and how they were checked
- [Ansible listings](listings/index.md) — the `--list-tags` and `--list-tasks` listings used in the validation phase
