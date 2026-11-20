---
title: Open questions
description: The open questions of the 2023.1 study, Q1 to Q14, each with why it matters and its status, either not available from the sources or answered from them.
tags: [unknowns, evidence, nova, libvirt, neutron, openvswitch, haproxy, keepalived, mariadb, keystone, glance, swift, bootstrap-servers, check-mode, scaling, images, one-shot]
---

# Open questions

The open questions of the study, Q1 to Q14. The summary table lists them, and each question has a section that gives
why it matters and its status.

> [!NOTE]
> **Key answers**
>
> - **Open questions [Q1–Q14](#q1):** all are [NOT AVAILABLE], except [Q14](#q14), which is answered from the source
>   [CODE], the control-flow part of [Q6](#q6), also answered from the source [CODE], and [Q10](#q10), whose 2023.1
>   form is partly answered: [F2](../reference/findings.md#f2) no longer applies, and the ansible-core 2.13 side is
>   not in these sources ([Questions](#questions)). [Q1](#q1) asks whether running VMs survive a `nova_libvirt`
>   restart or recreate.

## Summary

These questions cannot be settled by reading the sources, except Q14, which is answered in its section by reading the
kolla image sources. For Q6, the 2023.1 plays and the ansible-core 2.14.18 code answer whether later batches proceed;
the state of the failed node and the availability risk stay [NOT AVAILABLE]. Q10 was asked for the Ansible versions
Ussuri allows (2.8 and 2.9); 2023.1 allows ansible-core 2.13 and 2.14, and only 2.14.18 is in these sources, so its
2023.1 form is answered only in part. The others are [NOT AVAILABLE].

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
| **Status** | **Control flow answered from the source** [CODE]. In 2023.1 the handlers only put the hosts into the `mariadb_restart` and `mariadb_start` groups, and separate plays with `serial: "33%"` restart them; neither these plays nor any other MariaDB play sets `any_errors_fatal` or `max_fail_percentage` (`roles/mariadb/handlers/main.yml:56-73`, `mariadb.yml:14-40`). A node that fails its port or WSREP wait (`roles/mariadb/tasks/restart_services.yml:18-51`) marks only its own host failed. When that is every host of the batch (always so with three nodes, one host per batch), ansible-core ends the playbook and the later batches are not restarted; when other hosts of the batch succeed, the next batch still restarts its nodes (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:204-208`, `lib/ansible/utils/helpers.py:25-32`; [R9](../risk/risk-register.md#r9), [MariaDB](../components/mariadb.md#known-limits-and-open-points), [fact sheet B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order)). [NOT AVAILABLE] Whether the failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and availability risk is |

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
| **Why it matters** | Ussuri allows 2.8. 2023.1 no longer runs Ansible 2.8 or 2.9: `kolla-ansible` accepts ansible-core 2.13 to 2.14 (`tools/kolla-ansible:10-11`), so the question becomes whether 2.13 and 2.14 behave the same |
| **Status** | **Answered in part** [CODE]. [F2](../reference/findings.md#f2) no longer applies in 2023.1, whatever the Ansible version: `common` is its own play tagged `common` (`site.yml:86-97`), so `-t common` does not depend on tag inheritance through the dynamic `include_tasks` (`roles/common/tasks/main.yml:2`). [F1](../reference/findings.md#f1) holds in ansible-core 2.14.18: one changed loop item notifies the handlers of every executed item (`lib/ansible/plugins/strategy/__init__.py:614-621`, `lib/ansible/executor/task_executor.py:804-805`); the tag inheritance of dynamic includes is in `lib/ansible/playbook/task_include.py:131-150` and `lib/ansible/playbook/block.py:297-368` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [§2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). The Ussuri comparison (Ansible 2.8.20 against 2.9.27: same code for both findings) does not carry over. [NOT AVAILABLE] Whether ansible-core 2.13 has the same code: only 2.14.18 is in these sources |

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
| **Status** | **Answered from the source** [CODE], see [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run). Nova's bootstrap containers run with `KOLLA_UPGRADE`: `api_db sync` + `db sync --local_cell` (nova-api, whose bootstrap `nova.conf` points `[database]` at cell0), `db sync --local_cell` (nova-conductor), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure. New in 2023.1: nova-api's `KOLLA_UPGRADE_CHECK` runs `nova-status upgrade check`, upgrade only. Glance adds `db_load_metadefs`. Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone. neutron-server's `KOLLA_BOOTSTRAP` migrates neutron and every enabled subproject (networking-sfc, neutron-dynamic-routing, neutron-vpnaas, vmware-nsx), and the rolling upgrade migrates the same list, so the Ussuri gap on -dynamic-routing is closed (`roles/neutron/defaults/main.yml:656-664,705,711`). RabbitMQ writes the Erlang cookie only in its bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`). Agent, OVS and OVN images have no one-shot branch |

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
