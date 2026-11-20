---
title: Open questions
description: The open questions of the 2024.1 study, Q1 to Q21, each with why it matters and its status, either not available from the sources or answered from them.
tags: [unknowns, evidence, nova, libvirt, neutron, openvswitch, haproxy, keepalived, mariadb, rabbitmq, keystone, etcd, glance, swift, podman, bootstrap-servers, check-mode, scaling, images, one-shot]
---

# Open questions

The open questions of the study, Q1 to Q21. The summary table lists them, and each question has a section that gives
why it matters and its status. Q1 to Q14 are the questions of the 2023.1 study, re-checked against the 2024.1 sources;
Q15 to Q21 are new in 2024.1.

> [!NOTE]
> **Key answers**
>
> - **Open questions [Q1–Q21](#q1):** all are [NOT AVAILABLE], except [Q14](#q14), which is answered from the source
>   [CODE], the control-flow part of [Q6](#q6) and the handler part of [Q17](#q17), also answered from the source
>   [CODE], and [Q10](#q10), answered in part: [F2](../reference/findings.md#f2) no longer applies, and ansible-core
>   2.15 is not in these sources ([Questions](#questions)). [Q1](#q1) asks whether running VMs survive a
>   `nova_libvirt` restart or recreate.
> - **New in 2024.1:** how the Podman path behaves on a host ([Q15](#q15)), what oslo.messaging does with existing
>   classic queues under the new quorum-queue default ([Q16](#q16)), the real order of the staged etcd restarts
>   ([Q17](#q17)), where the Keystone `service` role comes from ([Q18](#q18)), what happens to containers of removed
>   services ([Q19](#q19)), what else drifts on the first 2024.1 run ([Q20](#q20)) and which RabbitMQ version a cloud
>   runs before its upgrade ([Q21](#q21)).

## Summary

These questions cannot be settled by reading the sources, except Q14, which is answered in its section by reading the
kolla image sources. For Q6, the 2024.1 plays and the ansible-core 2.16.20 code answer whether later batches proceed;
the state of the failed node and the availability risk stay [NOT AVAILABLE]. For Q17, the 2024.1 handlers show what
each host includes, not the order across hosts. Q10 was asked for the Ansible versions Ussuri allows (2.8 and 2.9);
2024.1 allows ansible-core 2.15 and 2.16, and only 2.16.20 is in these sources, so its 2024.1 form is answered only in
part. The others are [NOT AVAILABLE].

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
| [Q15](#q15) | New in 2024.1: behaviour of the Podman path on a host |
| [Q16](#q16) | New in 2024.1: existing classic queues under the quorum-queue default |
| [Q17](#q17) | New in 2024.1: real order of the staged etcd restarts |
| [Q18](#q18) | New in 2024.1: which step creates the Keystone `service` role |
| [Q19](#q19) | New in 2024.1: containers of removed services left on hosts |
| [Q20](#q20) | New in 2024.1: what else drifts on the first 2024.1 run of a 2023.1 cloud |
| [Q21](#q21) | New in 2024.1: RabbitMQ version before the upgrade, and the 3.12 step |

## Questions

<a id="q1"></a>

### Q1 — Do running VMs survive a `nova_libvirt` restart or recreate?

| | |
|---|---|
| **Question** | Do running VMs survive a `nova_libvirt` restart or recreate? |
| **Why it matters** | [F1](../reference/findings.md#f1) makes libvirt restarts frequent: any nova-cell drift on a compute restarts `nova_libvirt` with the rest of the role ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)) |
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
| **Why it matters** | [R7](../risk/risk-register.md#r7). New in 2024.1, a change of the `external_ids:hostname` key also notifies this restart (`roles/openvswitch/tasks/post-config.yml:3-23`, [Open vSwitch](../components/openvswitch.md#known-limits-and-open-points)) |
| **Status** | [NOT AVAILABLE] |

<a id="q4"></a>

### Q4 — L3 agent restart with and without `enable_neutron_agent_ha`

| | |
|---|---|
| **Question** | L3 agent restart with and without `enable_neutron_agent_ha` |
| **Why it matters** | [R6](../risk/risk-register.md#r6), [F12](../reference/findings.md#f12) |
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
| **Status** | **Control flow answered from the source** [CODE]. In 2024.1 the handlers only put the hosts into the `mariadb_restart` and `mariadb_start` groups, and separate plays with `serial: "33%"` restart them; no MariaDB play sets `any_errors_fatal`, and each sets `max_fail_percentage` from `mariadb_max_fail_percentage`, then `kolla_max_fail_percentage`, default 100 (`roles/mariadb/handlers/main.yml:55-72`, `mariadb.yml:18-52`). A node that fails its port or WSREP wait (`roles/mariadb/tasks/restart_services.yml:18-51`) marks only its own host failed. With the default of 100: when that is every host of the batch (always so with three nodes, one host per batch, ansible-core 2.16.20 `lib/ansible/utils/helpers.py:25-34`), ansible-core ends the playbook and the later batches are not restarted (`lib/ansible/executor/playbook_executor.py:204-209`, `:219-220`); when other hosts of the batch succeed, the next batch still restarts its nodes. **New in 2024.1:** with `-e mariadb_max_fail_percentage=0` (or `kolla_max_fail_percentage`), the first failed node marks the rest of its batch failed and ends the run before the next batch (`lib/ansible/plugins/strategy/linear.py:337-348`, `lib/ansible/executor/playbook_executor.py:196-198`) ([MariaDB](../components/mariadb.md#known-limits-and-open-points), [Controlled batches](../operations/controlled-batches.md), [fact sheet B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order)). [NOT AVAILABLE] Whether the failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and availability risk is |

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
| **Why it matters** | [Predict and inspect a run](../operations/predict-a-run.md#1-commands-and-what-they-show), [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code): `kolla_container`, which replaces `kolla_docker` in 2024.1, does not declare check-mode support (`library/kolla_container.py:355-359`), so ansible-core skips it under `--check` (`lib/ansible/module_utils/basic.py:506-507`) [CODE]; yet three `kolla_container` tasks set `check_mode: false` and start one-shot containers even under `--check` (`roles/nova-cell/tasks/get_cell_settings.yml:21`, `roles/rabbitmq/tasks/version-check.yml:36`, `roles/nova/tasks/upgrade.yml:30`) [CODE] |
| **Status** | [NOT AVAILABLE] |

<a id="q10"></a>

### Q10 — Ansible 2.8 vs 2.9 behaviour for F1/F2

| | |
|---|---|
| **Question** | Ansible 2.8 vs 2.9 behaviour for [F1](../reference/findings.md#f1)/[F2](../reference/findings.md#f2) |
| **Why it matters** | Ussuri allows 2.8. 2024.1 no longer runs Ansible 2.8 or 2.9: `kolla-ansible` accepts ansible-core 2.15 to 2.16 (`tools/kolla-ansible:10-11`), so the question becomes whether 2.15 and 2.16 behave the same |
| **Status** | **Answered in part** [CODE]. [F2](../reference/findings.md#f2) no longer applies in 2024.1, whatever the Ansible version: `common` is its own play tagged `common` (`site.yml:88-103`), so `-t common` does not depend on tag inheritance through the dynamic `include_tasks` (`roles/common/tasks/main.yml:2`). [F1](../reference/findings.md#f1) holds in ansible-core 2.16.20: one changed loop item notifies the handlers of every executed item (`lib/ansible/plugins/strategy/__init__.py:648-673`, `lib/ansible/executor/task_executor.py:816-820`); the tag inheritance of dynamic includes is in `lib/ansible/playbook/block.py:294-361` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [§2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). The 2023.1 answer, read in ansible-core 2.14.18, does not carry over. [NOT AVAILABLE] Whether ansible-core 2.15 has the same code: only 2.16.20 is in these sources |

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
| **Status** | **Answered from the source** [CODE], see [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run). Still holds in 2024.1: Nova's bootstrap containers run with `KOLLA_UPGRADE` (`roles/nova/tasks/bootstrap_service.yml:10-11`, `roles/nova-cell/tasks/bootstrap_service.yml:10-11`): `api_db sync` + `db sync --local_cell` (nova-api, kolla `docker/nova/nova-api/extend_start.sh:16-20`), `db sync --local_cell` (nova-conductor, kolla `docker/nova/nova-conductor/extend_start.sh:9-12`), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure (`roles/placement/tasks/bootstrap_service.yml:11`, kolla `docker/placement/placement-api/extend_start.sh:5-9`). nova-api's `KOLLA_UPGRADE_CHECK` runs `nova-status upgrade check`, upgrade only (`roles/nova/tasks/upgrade.yml:18`, kolla `docker/nova/nova-api/extend_start.sh:27-30`). Glance adds `db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`). Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone (kolla `docker/heat/heat-api/extend_start.sh:5-17`). neutron-server's `KOLLA_BOOTSTRAP` migrates neutron and every enabled subproject, and the rolling upgrade migrates the same list; **changed in 2024.1**, the list adds neutron-fwaas and tap-as-a-service to networking-sfc, neutron-dynamic-routing, neutron-vpnaas and vmware-nsx (`roles/neutron/defaults/main.yml:674-686,727,733`). **New in 2024.1**, octavia-api's `KOLLA_BOOTSTRAP` also runs `octavia-db-manage upgrade_persistence` (kolla `docker/octavia/octavia-api/extend_start.sh:5-9`). RabbitMQ writes the Erlang cookie only in its bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`). Agent, OVS and OVN images have no one-shot branch |

<a id="q15"></a>

### Q15 — Behaviour of the Podman path on a host

**New in 2024.1.**

| | |
|---|---|
| **Question** | How do the Podman worker, the Podman Python client, Podman and systemd behave on a real host when `kolla_container_engine: podman`? |
| **Why it matters** | `kolla_container_engine` defaults to `"docker"` (`group_vars/all.yml:92`), and any other value makes `kolla_container` use the Podman worker (`library/kolla_container.py:415-420`), which talks to the Podman socket through the Podman Python client (`module_utils/kolla_podman_worker.py:21,73`) [CODE]. With Podman the worker writes and enables a systemd unit at creation for every container, one-shots included (`module_utils/kolla_podman_worker.py:497-505`), and stops every long-running container through its unit (`:575-593`); image pruning becomes a `podman image prune` command ([Update container images §1.2](../operations/update-container-images.md#12-prune-old-images)). Every Podman statement of the study is code-only ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container), [Limits of the study](../reference/method-and-limits.md#limits-of-this-study)) |
| **Status** | [NOT AVAILABLE] The Podman Python client, Podman and systemd are not in these sources, and no Podman host was used |

<a id="q16"></a>

### Q16 — Existing classic queues under the quorum-queue default

**New in 2024.1.**

| | |
|---|---|
| **Question** | What does oslo.messaging do with existing classic queues when the services restart with `rabbit_quorum_queue = true`? |
| **Why it matters** | [F17](../reference/findings.md#f17): `om_enable_rabbitmq_quorum_queues` defaults to `true` (`group_vars/all.yml:266-268`), so a cloud that kept the 2023.1 default gets a changed messaging config, and a restart, for every service that renders `[oslo_messaging_rabbit]`. `prechecks` fails when HA and quorum are equal (`roles/prechecks/tasks/service_checks.yml:67-72`) and, with quorum on, asserts that every queue except `reply_` and `_fanout` ones is a quorum queue; its message calls the migration manual (`roles/rabbitmq/tasks/precheck.yml:131-152,185-189`) [CODE] ([RabbitMQ](../components/rabbitmq.md#impact-and-risk), [Pre-execution checklist §2](../operations/pre-execution-checklist.md#2-first-20241-run-on-a-cloud-deployed-by-20231)) |
| **Status** | [NOT AVAILABLE] oslo.messaging is not in these sources; nor is how long a manual migration takes |

<a id="q17"></a>

### Q17 — Real order of the staged etcd restarts

**New in 2024.1.**

| | |
|---|---|
| **Question** | In which order do the etcd members really restart, on `upgrade` and outside it, and do etcd clients fail meanwhile? |
| **Why it matters** | The etcd play has no `serial` (`site.yml:470-481`), so `ANSIBLE_SERIAL` does not batch it; quorum depends on the order of the handler restarts ([Controlled batches §1.2](../operations/controlled-batches.md#12-rolling-reconfigure-with-ansible_serial), [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)) |
| **Status** | **Handlers answered from the source** [CODE]. The handlers look up the leader (`roles/etcd/handlers/main.yml:9-17`); outside `upgrade` and `config` they restart the non-leaders in a loop over the four values of `groups.etcd.index(host) % 4` (`:38-55`), then the leader, whose handler is defined last (`:57-65`). On `upgrade` the non-leader handler loops over `groups.etcd` without using `item` (`:28-36`), so each non-leader includes the restart tasks once per etcd member; its comment says "one by one". Each restart waits for the client port and for `etcdctl endpoint health` (`roles/etcd/tasks/restart_services.yml:16-41`). [NOT AVAILABLE] How ansible-core orders, across hosts, the files included by one looped handler, so whether the `% 4` waves really restart one after another and whether the `upgrade` restarts are really one by one; whether etcd clients fail while the members restart |

<a id="q18"></a>

### Q18 — Which step creates the Keystone `service` role

**New in 2024.1.**

| | |
|---|---|
| **Question** | Which step creates the Keystone `service` role that 2024.1 roles grant to their users? |
| **Why it matters** | The nova role no longer creates the role itself (2023.1 passed `nova_ks_roles: [service]`) but still grants it to `nova` (`roles/nova/tasks/register.yml:2-8`, `roles/nova/defaults/main.yml:253-256`); `service-ks-register` creates only the roles of its users plus `service_ks_register_roles`, empty by default (`roles/service-ks-register/tasks/main.yml:87-97`, `roles/service-ks-register/defaults/main.yml:29`) [CODE] ([Nova deep dive §2.1](../components/nova-deep-dive.md#21-installation-deploy-time-dependencies)) |
| **Status** | [NOT AVAILABLE] No Kolla-Ansible task found passes it, and the Keystone sources, where its own bootstrap is defined, are not part of this study |

<a id="q19"></a>

### Q19 — Containers of removed services left on hosts

**New in 2024.1.**

| | |
|---|---|
| **Question** | What happens to a `chrony` container, or to a container of a service removed in 2024.1, left on a host by an earlier release? |
| **Why it matters** | 2024.1 has no chrony role or play, and no file under `ansible/` or `tools/` names freezer, monasca, murano, sahara, senlin, solum, vitrage, kafka, storm, zookeeper or outward RabbitMQ; the only `chrony` reference is the precheck that looks for an active host time daemon (`roles/prechecks/tasks/timesync_checks.yml:1-47`) [CODE]. So no tagged run stops, removes or checks those containers ([Chrony](../components/chrony.md#known-limits-and-open-points), [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row "removed services") |
| **Status** | [NOT AVAILABLE] What such a container does on a host, for example a `chrony` container next to the host NTP daemon that the precheck requires |

<a id="q20"></a>

### Q20 — What else drifts on the first 2024.1 run of a 2023.1 cloud

**New in 2024.1.**

| | |
|---|---|
| **Question** | Besides the unit change of [F16](../reference/findings.md#f16), what makes containers differ on the first 2024.1 `deploy`, `reconfigure` or `deploy-containers` of a cloud deployed by 2023.1, and how does the new unit behave? |
| **Why it matters** | [F16](../reference/findings.md#f16): the 2024.1 unit template differs from the 2023.1 one and the whole unit text is compared, so every container whose unit 2023.1 wrote is restarted at its first check (`module_utils/kolla_systemd_worker.py:20-39,154-167`) [CODE]. The `nova_libvirt` bind of `/run` is now written `/run:/run:shared` with Docker (`roles/nova-cell/defaults/main.yml:374`; 2023.1 `/run/:/run/:shared`), and the Docker worker compares the bind strings as sets, without normalising them (`module_utils/kolla_docker_worker.py:124-144`) [CODE] ([Nova](../components/nova.md#what-changed-in-20241), [iSCSI](../components/iscsi.md#known-limits-and-open-points), [Predict and inspect a run §2](../operations/predict-a-run.md#2-the-first-20241-run-on-a-cloud-deployed-by-20231)) |
| **Status** | [NOT AVAILABLE] Whether Docker reports the 2023.1 `/run/` binds with their trailing slash, and so whether they alone make `nova_libvirt` and `iscsid` differ; whether systemd treats the 2023.1 `StartLimitIntervalSec=` and the 2024.1 `StartLimitInterval=` key the same ([Kolla images §2.3](../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions)) |

<a id="q21"></a>

### Q21 — RabbitMQ version before the upgrade, and the 3.12 step

**New in 2024.1.**

| | |
|---|---|
| **Question** | Which RabbitMQ version does a cloud run before its first 2024.1 run, and which image would a `kolla-ansible rabbitmq-upgrade 3.12` run with 2024.1 code find? |
| **Why it matters** | `upgrade` now runs the version check first (`roles/rabbitmq/tasks/upgrade.yml:2`), which fails unless the running version is at most one minor version behind the target, or the step is 3.13 to 4.0 or 4.1, and names the `rabbitmq-upgrade` step to run first (`roles/rabbitmq/tasks/version-check.yml:44-64`) [CODE]. The 2024.1 `rabbitmq` image pins RabbitMQ 3.13 (kolla `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:2`), the 2023.1 one pinned 3.11, and the kolla 2024.1 tree has no `rabbitmq-3-12` image [CODE] ([RabbitMQ](../components/rabbitmq.md#before-and-after-a-run)) |
| **Status** | [NOT AVAILABLE] The running version is a property of each cloud, and the registry content is not in these sources |

## Related

- [What is not known](what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic, with the sections that mark
  each point
- [Risk register](../risk/risk-register.md) — the risks that the "Why it matters" rows cite
- [Findings](../reference/findings.md) — the findings that Q1, Q10, Q14, Q16 and Q20 cite:
  [F1](../reference/findings.md#f1), [F2](../reference/findings.md#f2), [F5](../reference/findings.md#f5),
  [F15](../reference/findings.md#f15), [F16](../reference/findings.md#f16) and [F17](../reference/findings.md#f17)
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — the answer
  to [Q14](#q14): what the one-shot containers run in each image
- [Compute scaling](../concepts/compute-scaling-and-performance.md) — the model that [Q7](#q7) and [Q8](#q8) concern
- [Limits of this study](../reference/method-and-limits.md#limits-of-this-study) — source code only, the Podman path
  read in the code only: why these questions cannot be settled here
- [Fact sheet E
  §14](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#14-register-of-open-questions-not-available-or-answered-from-code)
  — the register of open questions of fact sheet E
