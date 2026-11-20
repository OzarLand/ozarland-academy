---
title: Open questions
description: The open questions of the study, Q1 to Q14, each with why it matters and its status, either not available from the sources or answered from them.
tags: [unknowns, evidence, nova, libvirt, neutron, openvswitch, haproxy, keepalived, mariadb, keystone, glance, swift, bootstrap-servers, check-mode, scaling, images, one-shot]
---

# Open questions

The open questions of the study, Q1 to Q14. The summary table lists them, and each question has a section that gives
why it matters and its status.

> [!NOTE]
> **Key answers**
>
> - **Open questions [Q1–Q14](#q1):** all are [NOT AVAILABLE], except [Q10](#q10) and [Q14](#q14), which are answered
>   from the source [CODE], and the control-flow part of [Q6](#q6), which is also answered from the source [CODE]
>   ([Questions](#questions)). [Q1](#q1) asks whether running VMs survive a `nova_libvirt` restart or recreate.

## Summary

These questions cannot be settled by reading the sources, except Q10 and Q14, which are answered from the source in
their sections: Q10 by comparing the Ansible 2.8.20 and 2.9.27 code, Q14 by reading the kolla image sources. For Q6,
the Ansible 2.9.27 code answers whether later waves proceed; the state of the failed node and the availability risk
stay [NOT AVAILABLE]. The others are [NOT AVAILABLE].

| # | Question |
|---|---|
| [Q1](#q1) | Do running VMs survive a `nova_libvirt` restart or recreate? |
| [Q2](#q2) | Data-plane loss during a `neutron_openvswitch_agent` restart |
| [Q3](#q3) | Data-plane loss during an `openvswitch_vswitchd` restart or recreate |
| [Q4](#q4) | L3 agent restart with and without `enable_neutron_agent_ha` |
| [Q5](#q5) | HAProxy restart: VIP behaviour |
| [Q6](#q6) | MariaDB rolling restart under load with a failure in wave 1: do later waves proceed? |
| [Q7](#q7) | Real timing at scale (SSH, pipelining, fact caching, forks) |
| [Q8](#q8) | Image sizes and registry throughput |
| [Q9](#q9) | Check mode (`--check --diff`) usability |
| [Q10](#q10) | Ansible 2.8 vs 2.9 behaviour for [F1](../reference/findings.md#f1)/[F2](../reference/findings.md#f2) |
| [Q11](#q11) | Fernet key distribution failure modes |
| [Q12](#q12) | Glance backend switch on enabling Swift |
| [Q13](#q13) | `bootstrap-servers` re-run effects on a live compute |
| [Q14](#q14) | Behaviour of the kolla images' `extend_start.sh` (what `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` run) |

## Questions

<a id="q1"></a>

### Q1 — Do running VMs survive a `nova_libvirt` restart or recreate?

| | |
|---|---|
| **Question** | Do running VMs survive a `nova_libvirt` restart or recreate? |
| **Why it matters** | [F1](../reference/findings.md#f1) makes libvirt restarts frequent |
| **Status** | [NOT AVAILABLE] |

<a id="q2"></a>

### Q2 — Data-plane loss during a `neutron_openvswitch_agent` restart

| | |
|---|---|
| **Question** | Data-plane loss during a `neutron_openvswitch_agent` restart |
| **Why it matters** | [R5](../risk/risk-register.md#r5) |
| **Status** | [NOT AVAILABLE] |

<a id="q3"></a>

### Q3 — Data-plane loss during an `openvswitch_vswitchd` restart or recreate

| | |
|---|---|
| **Question** | Data-plane loss during an `openvswitch_vswitchd` restart or recreate |
| **Why it matters** | [R7](../risk/risk-register.md#r7) |
| **Status** | [NOT AVAILABLE] |

<a id="q4"></a>

### Q4 — L3 agent restart with and without `enable_neutron_agent_ha`

| | |
|---|---|
| **Question** | L3 agent restart with and without `enable_neutron_agent_ha` |
| **Why it matters** | [R6](../risk/risk-register.md#r6) |
| **Status** | [NOT AVAILABLE] |

<a id="q5"></a>

### Q5 — HAProxy restart: VIP behaviour

| | |
|---|---|
| **Question** | HAProxy restart: VIP behaviour |
| **Why it matters** | [R8](../risk/risk-register.md#r8) |
| **Status** | [NOT AVAILABLE] |

<a id="q6"></a>

### Q6 — MariaDB rolling restart under load, failure in wave 1: do later waves proceed?

| | |
|---|---|
| **Question** | MariaDB rolling restart under load with a failure in wave 1: do later waves proceed? |
| **Why it matters** | [R9](../risk/risk-register.md#r9) |
| **Status** | **Control flow answered from the source** [CODE]: a node that fails its WSREP wait marks only its own host failed, and the next wave still restarts its nodes (`roles/mariadb/handlers/main.yml:66-78`, `roles/mariadb/tasks/restart_services.yml:28-39`; ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:548-561,1019-1020,1045-1063`; no MariaDB play sets `any_errors_fatal`; [R9](../risk/risk-register.md#r9), [fact sheet B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order)). [NOT AVAILABLE] Whether the failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and availability risk is |

<a id="q7"></a>

### Q7 — Real timing at scale

| | |
|---|---|
| **Question** | Real timing at scale (SSH, pipelining, fact caching, forks) |
| **Why it matters** | [Compute scaling](../concepts/compute-scaling-and-performance.md) model |
| **Status** | [NOT AVAILABLE] |

<a id="q8"></a>

### Q8 — Image sizes and registry throughput

| | |
|---|---|
| **Question** | Image sizes and registry throughput |
| **Why it matters** | [Compute scaling](../concepts/compute-scaling-and-performance.md) model |
| **Status** | [NOT AVAILABLE] |

<a id="q9"></a>

### Q9 — Check mode (`--check --diff`) usability

| | |
|---|---|
| **Question** | Check mode (`--check --diff`) usability |
| **Why it matters** | [Operations](../operations/index.md), [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code): `kolla_docker` is skipped under `--check` [CODE] |
| **Status** | [NOT AVAILABLE] |

<a id="q10"></a>

### Q10 — Ansible 2.8 vs 2.9 behaviour for F1/F2

| | |
|---|---|
| **Question** | Ansible 2.8 vs 2.9 behaviour for [F1](../reference/findings.md#f1)/[F2](../reference/findings.md#f2) |
| **Why it matters** | Ussuri allows 2.8 |
| **Status** | **Answered from the source** [CODE]: the code that produces [F1](../reference/findings.md#f1) and [F2](../reference/findings.md#f2) is the same in both versions. Loop notify: ansible 2.8.20 `lib/ansible/plugins/strategy/__init__.py:540-557` matches 2.9.27 `:609-626`, and `_ansible_notify` is set the same way (2.8.20 `lib/ansible/executor/task_executor.py:784`, 2.9.27 `:790`). Tag inheritance: `Task._get_parent_attribute`, `Block._get_parent_attribute` and `TaskInclude.build_parent_block` (2.8.20 `lib/ansible/playbook/task.py:427-458`, `block.py:300-364`, `task_include.py:124-143`) match 2.9.27's `task.py:458-489`, `block.py:300-364` and `task_include.py:135-154` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [§2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) |

<a id="q11"></a>

### Q11 — Fernet key distribution failure modes

| | |
|---|---|
| **Question** | Fernet key distribution failure modes |
| **Why it matters** | [R19](../risk/risk-register.md#r19) |
| **Status** | [NOT AVAILABLE] |

<a id="q12"></a>

### Q12 — Glance backend switch on enabling Swift

| | |
|---|---|
| **Question** | Glance backend switch on enabling Swift |
| **Why it matters** | [R21](../risk/risk-register.md#r21) |
| **Status** | [NOT AVAILABLE] |

<a id="q13"></a>

### Q13 — `bootstrap-servers` re-run effects on a live compute

| | |
|---|---|
| **Question** | `bootstrap-servers` re-run effects on a live compute |
| **Why it matters** | [R14](../risk/risk-register.md#r14) |
| **Status** | [NOT AVAILABLE] |

<a id="q14"></a>

### Q14 — Behaviour of the kolla images' `extend_start.sh`

| | |
|---|---|
| **Question** | Behaviour of the kolla images' `extend_start.sh` (what `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` run) |
| **Why it matters** | [F5](../reference/findings.md#f5), [F15](../reference/findings.md#f15) |
| **Status** | **Answered from the source** [CODE], see [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run). Nova's bootstrap containers run with `KOLLA_UPGRADE`: `api_db sync` + `db sync` (nova-api), `db sync --local_cell` (nova-conductor), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure. Glance adds `db_load_metadefs`. Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone. neutron-server's `KOLLA_BOOTSTRAP` migrates neutron, -dynamic-routing, -fwaas and -vpnaas; the rolling upgrade list omits -dynamic-routing. RabbitMQ writes the Erlang cookie only in its bootstrap container. Agent, OVS and OVN images have no one-shot branch |

## Related

- [What is not known](what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic, with the sections that mark
  each point
- [Risk register](../risk/risk-register.md) — the risks that the "Why it matters" rows cite
- [Findings](../reference/findings.md) — the findings that Q1, Q10 and Q14 cite: [F1](../reference/findings.md#f1),
  [F2](../reference/findings.md#f2), [F5](../reference/findings.md#f5) and [F15](../reference/findings.md#f15)
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — the answer
  to [Q14](#q14): what the one-shot containers run in each image
- [Compute scaling](../concepts/compute-scaling-and-performance.md) — the model that [Q7](#q7) and [Q8](#q8) concern
- [Limits of this study](../reference/method-and-limits.md#limits-of-this-study) — source code only: why these
  questions cannot be settled here
- [Fact sheet E
  §14](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#14-register-of-open-questions-not-available-or-answered-from-code)
  — the register of open questions of fact sheet E
