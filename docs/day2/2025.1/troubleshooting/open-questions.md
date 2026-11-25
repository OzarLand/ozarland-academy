---
title: Open questions
description: The open questions of the 2025.1 study, Q1 to Q23, each with why it matters and its status, either not available from the sources, answered or obsolete.
tags: [unknowns, evidence, nova, libvirt, virtlogd, neutron, openvswitch, haproxy, keepalived, mariadb, rabbitmq, keystone, etcd, glance, podman, bootstrap-servers, check-mode, scaling, images, one-shot, kolla-set-configs]
---

# Open questions

The open questions of the study, Q1 to Q23. The summary table lists them, and each question has a section that gives
why it matters and its status. Q1 to Q21 are the questions of the 2024.1 study, re-checked against the 2025.1 sources;
Q22 and Q23 are new in 2025.1.

> [!NOTE]
> **Key answers**
>
> - **Open questions [Q1–Q23](#q1):** all are [NOT AVAILABLE], except [Q14](#q14), which is answered from the source
>   [CODE], the control-flow part of [Q6](#q6) and the handler part of [Q17](#q17), also answered from the source
>   [CODE], [Q10](#q10), answered in part, and [Q12](#q12), which no longer applies: Swift is gone from 2025.1
>   ([Questions](#questions)). [Q1](#q1) asks whether running VMs survive a `nova_libvirt` restart or recreate.
> - **Changed in 2025.1:** [Q1](#q1) and [Q3](#q3) gain a part (virtlogd now runs in `nova_libvirt`; `ovs_wrapper` now
>   runs the Open vSwitch daemons), [Q4](#q4) depends on the new `neutron_agents_wrappers`, [Q16](#q16) narrows
>   because quorum queues are now the only choice, and [Q20](#q20) and [Q21](#q21) now concern the step from 2024.1 to
>   2025.1.
> - **New in 2025.1:** what a `nova_libvirt` restart does to guest console logging now that virtlogd runs in the
>   container ([Q22](#q22)), and whether the dropped-entry check really restarts a container on every run until it is
>   recreated ([Q23](#q23)).

## Summary

These questions cannot be settled by reading the sources, except Q14, which is answered in its section by reading the
kolla image sources. For Q6, the 2025.1 plays and the ansible-core 2.18.20 code answer whether later batches proceed;
the state of the failed node and the availability risk stay [NOT AVAILABLE]. For Q17, the 2025.1 handlers show what
each host includes, not the order across hosts. Q10 was asked for the Ansible versions Ussuri allows (2.8 and 2.9);
2025.1 allows ansible-core 2.17 and 2.18, and only 2.18.20 is in these sources, so its 2025.1 form is answered only in
part. Q12 concerned Swift, which 2025.1 no longer deploys. The others are [NOT AVAILABLE].

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
| [Q12](#q12) | Glance backend switch on enabling Swift (no longer applies in 2025.1) |
| [Q13](#q13) | `bootstrap-servers` re-run effects on a live compute |
| [Q14](#q14) | Behaviour of the kolla images' `extend_start.sh` (what `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` run) |
| [Q15](#q15) | From 2024.1: behaviour of the Podman path on a host |
| [Q16](#q16) | From 2024.1: existing classic queues under the quorum-queue default |
| [Q17](#q17) | From 2024.1: real order of the staged etcd restarts |
| [Q18](#q18) | From 2024.1: which step creates the Keystone `service` role |
| [Q19](#q19) | From 2024.1: containers of removed services left on hosts |
| [Q20](#q20) | What else drifts on the first 2025.1 run of a 2024.1 cloud |
| [Q21](#q21) | RabbitMQ version before the upgrade, and the step to 4.0 |
| [Q22](#q22) | New in 2025.1: guest console logging across a `nova_libvirt` restart |
| [Q23](#q23) | New in 2025.1: does a dropped `config.json` entry restart a container on every run? |

## Questions

<a id="q1"></a>

### Q1 — Do running VMs survive a `nova_libvirt` restart or recreate?

| | |
|---|---|
| **Question** | Do running VMs survive a `nova_libvirt` restart or recreate? |
| **Why it matters** | In 2025.1 [F1](../reference/findings.md#f1) no longer holds, so `nova_libvirt` restarts only when its own check reports a change, but that check now also fires on a changed command, and on every run after a dropped entry until the container is recreated ([F21](../reference/findings.md#f21)). The first 2025.1 run changes its command to `kolla_nova_libvirt_start`, so every `nova_libvirt` restarts or is recreated then ([Kolla images §5.1](../concepts/kolla-images.md#51-nova-libvirt-the-start-path-is-passive), [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)) |
| **Status** | [NOT AVAILABLE] |
| **Outside this study** | The runbook [Restarting nova_libvirt does not stop instances](../../../runbooks/lifecycle/restarting-nova-libvirt-does-not-stop-instances/) and [lab exercise 4](../../../lab/exercises/04-restart-nova-libvirt/) restart `nova_libvirt` on a lab and report that the instances kept running (observed on 2026.1). It is an observation on another release (2026.1), not evidence for 2025.1: this study stays [NOT AVAILABLE]. |

<a id="q2"></a>

### Q2 — Data-plane loss during a `neutron_openvswitch_agent` restart

| | |
|---|---|
| **Question** | Data-plane loss during a `neutron_openvswitch_agent` restart |
| **Why it matters** | [R5](../risk/risk-register.md#r5) |
| **Status** | [NOT AVAILABLE] |
| **Outside this study** | The runbook [Restarting the OVS agent does not cut instances](../../../runbooks/networking/restarting-the-ovs-agent-does-not-cut-instances/) and [lab exercise 5](../../../lab/exercises/05-restart-ovs-agent/) restart the Open vSwitch agent on a lab and report no lost request (observed on 2026.1). It is an observation on another release (2026.1), not evidence for 2025.1: this study stays [NOT AVAILABLE]. |

<a id="q3"></a>

### Q3 — Data-plane loss during an `openvswitch_vswitchd` restart or recreate

| | |
|---|---|
| **Question** | Data-plane loss during an `openvswitch_vswitchd` restart or recreate |
| **Why it matters** | [R7](../risk/risk-register.md#r7). A change of the `system-id` or `hostname` external ids, or of `hw-offload`, notifies this restart (`roles/openvswitch/tasks/post-config.yml:3-23`). **Changed in 2025.1:** both Open vSwitch containers run under kolla's `ovs_wrapper` instead of Kolla-Ansible's `start-ovs` scripts, and its stop handler does not reach the daemon, so `ovs-vswitchd` ends without its own shutdown ([F22](../reference/findings.md#f22), [Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)) [CODE] |
| **Status** | [NOT AVAILABLE] |
| **Outside this study** | The runbook [ovs-vswitchd down on a compute](../../../runbooks/networking/ovs-vswitchd-down-on-compute/) stops and starts `openvswitch_vswitchd` on a lab and reports that the instances of the compute lose the network until the agent has programmed the flows again (observed on 2026.1). It is an observation on another release (2026.1), not evidence for 2025.1: this study stays [NOT AVAILABLE]. |

<a id="q4"></a>

### Q4 — L3 agent restart with and without `enable_neutron_agent_ha`

| | |
|---|---|
| **Question** | L3 agent restart with and without `enable_neutron_agent_ha`, and, new in 2025.1, with `neutron_agents_wrappers` |
| **Why it matters** | [R6](../risk/risk-register.md#r6), [F12](../reference/findings.md#f12). New in 2025.1, `neutron_agents_wrappers` (default `no`) runs the agents' keepalived, haproxy, radvd and dnsmasq in child containers and skips the start-time `neutron-netns-cleanup` (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16`, `roles/neutron/defaults/main.yml:646`; [Kolla images §2.5](../concepts/kolla-images.md#25-the-extend_start-chain)) [CODE] |
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
| **Status** | **Control flow answered from the source** [CODE], unchanged from 2024.1. The handlers only put the hosts into the `mariadb_restart` and `mariadb_start` groups, and separate plays with `serial: "33%"` restart them; no MariaDB play sets `any_errors_fatal`, and each sets `max_fail_percentage` from `mariadb_max_fail_percentage`, then `kolla_max_fail_percentage`, default 100 (`roles/mariadb/handlers/main.yml:59-74`, `mariadb.yml:18-52`). A node that fails its port or WSREP wait (`roles/mariadb/tasks/restart_services.yml:18-53`) marks only its own host failed. With the default of 100: when that is every host of the batch (always so with three nodes, one host per batch, ansible-core 2.18.20 `lib/ansible/utils/helpers.py:23-32`), ansible-core ends the playbook and the later batches are not restarted (`lib/ansible/executor/playbook_executor.py:198-204`, `:214-215`); when other hosts of the batch succeed, the next batch still restarts its nodes. With `-e mariadb_max_fail_percentage=0` (or `kolla_max_fail_percentage`), the first failed node marks the rest of its batch failed and ends the run before the next batch (`lib/ansible/plugins/strategy/linear.py:335-349`, `lib/ansible/executor/playbook_executor.py:193-196`) ([MariaDB](../components/mariadb.md#known-limits-and-open-points), [Controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage), [fact sheet B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order)). [NOT AVAILABLE] Whether the failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and availability risk is |

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
| **Why it matters** | [Predict and inspect a run](../operations/predict-a-run.md#1-commands-and-what-they-show), [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code): `kolla_container` does not declare check-mode support (`library/kolla_container.py:351-355`), so ansible-core skips it under `--check` (ansible-core 2.18.20 `lib/ansible/module_utils/basic.py:447-448`) [CODE]; yet five `kolla_container` tasks set `check_mode: false` and start one-shot containers even under `--check`, two of them new in 2025.1 (`roles/nova-cell/tasks/get_cell_settings.yml:21`, `roles/nova-cell/tasks/version-check.yml:19,96`, `roles/rabbitmq/tasks/version-check.yml:37`, `roles/nova/tasks/upgrade.yml:26`) [CODE]. The new `kolla-ansible check` command is not check mode: it runs normally and only reads container facts ([Kolla images §2.7](../concepts/kolla-images.md#27-healthcheck-scripts)) |
| **Status** | [NOT AVAILABLE] |

<a id="q10"></a>

### Q10 — Ansible 2.8 vs 2.9 behaviour for F1/F2

| | |
|---|---|
| **Question** | Ansible 2.8 vs 2.9 behaviour for [F1](../reference/findings.md#f1)/[F2](../reference/findings.md#f2) |
| **Why it matters** | Ussuri allows 2.8. 2025.1 no longer runs Ansible 2.8 or 2.9: its Python package requires ansible-core 2.17 or 2.18 (`requirements.txt:14`; the 2024.1 shell script `tools/kolla-ansible` is gone), so the question becomes whether 2.17 and 2.18 behave the same |
| **Status** | **Answered in part** [CODE]. [F2](../reference/findings.md#f2) no longer applies, whatever the Ansible version: `common` is its own play tagged `common` (`site.yml:88-103`). **Changed in 2025.1:** [F1](../reference/findings.md#f1) no longer holds either, also whatever the version, because the config tasks no longer notify and `service-check-containers` notifies only the items reported changed (`roles/service-check-containers/tasks/main.yml:34-41`; [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). The loop-notify behaviour itself is unchanged in ansible-core 2.18.20 (`lib/ansible/plugins/strategy/__init__.py:648-661`, `lib/ansible/executor/task_executor.py:850-851`), and the tag inheritance of dynamic includes is in `lib/ansible/playbook/block.py:309-359` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)). [NOT AVAILABLE] Whether ansible-core 2.17 has the same code: only 2.18.20 is in these sources |

<a id="q11"></a>

### Q11 — Fernet key distribution failure modes

| | |
|---|---|
| **Question** | Fernet key distribution failure modes |
| **Why it matters** | [R19](../risk/risk-register.md#r19) |
| **Status** | [NOT AVAILABLE] |

<a id="q12"></a>

### Q12 — Glance backend switch on enabling Swift

**No longer applies in 2025.1.**

| | |
|---|---|
| **Question** | Glance backend switch on enabling Swift |
| **Why it matters** | [R21](../risk/risk-register.md#r21). 2025.1 has no `swift` role, and the glance defaults no longer mention Swift (no `swift` in `roles/glance/defaults/main.yml`) [CODE] |
| **Status** | No longer applies: Kolla-Ansible 2025.1 cannot enable Swift. A cloud that ran Swift with 2024.1 is covered by [Q19](#q19) |

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
| **Status** | **Answered from the source** [CODE], see [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run). Still holds in 2025.1: Nova's bootstrap containers run with `KOLLA_UPGRADE` (`roles/nova/tasks/bootstrap_service.yml:10-11`, `roles/nova-cell/tasks/bootstrap_service.yml:10-11`): `api_db sync` + `db sync --local_cell` (nova-api, kolla `docker/nova/nova-api/extend_start.sh:16-20`), `db sync --local_cell` (nova-conductor, kolla `docker/nova/nova-conductor/extend_start.sh:9-12`), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure (`roles/placement/tasks/bootstrap_service.yml:11`, kolla `docker/placement/placement-api/extend_start.sh:5-9`). Glance adds `db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`). Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone (kolla `docker/heat/heat-api/extend_start.sh:5-17`). neutron-server's `KOLLA_BOOTSTRAP` migrates neutron and every enabled subproject, the same list as the rolling upgrade (`roles/neutron/defaults/main.yml:651-663,702,708`). octavia-api's bootstrap runs `upgrade head` and `upgrade_persistence` (kolla `docker/octavia/octavia-api/extend_start.sh:5-9`). RabbitMQ writes the Erlang cookie only in its bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`). Agent, OVS and OVN images have no one-shot branch. **New in 2025.1:** every one-shot that runs `kolla_start` also runs `kolla_install_projects`, and two nova-libvirt one-shots, `libvirt_version_check` and `nova_libvirt_script_check`, replace `kolla_start` with their own command (`roles/nova-cell/tasks/version-check.yml:2-120`; [Kolla images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start)) |

<a id="q15"></a>

### Q15 — Behaviour of the Podman path on a host

**From 2024.1.**

| | |
|---|---|
| **Question** | How do the Podman worker, the Podman Python client, Podman and systemd behave on a real host when `kolla_container_engine: podman`? |
| **Why it matters** | `kolla_container_engine` defaults to `"docker"` (`group_vars/all.yml:100`), and any other value makes `kolla_container` use the Podman worker (`library/kolla_container.py:411-416`), which talks to the Podman socket through the Podman Python client (`module_utils/kolla_podman_worker.py:21,73`) [CODE]. With Podman the worker writes and enables a systemd unit at creation for every container, one-shots included (`module_utils/kolla_podman_worker.py:596-607`), and stops every long-running container through its unit (`:677-695`). In 2025.1 the neutron agent wrappers also start child containers through the Podman socket ([Kolla images §2.5](../concepts/kolla-images.md#25-the-extend_start-chain)). Every Podman statement of the study is code-only ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container), [Limits of the study](../reference/method-and-limits.md#limits-of-this-study)) |
| **Status** | [NOT AVAILABLE] The Podman Python client, Podman and systemd are not in these sources, and no Podman host was used |

<a id="q16"></a>

### Q16 — Existing classic queues under the quorum-queue default

**From 2024.1; narrower in 2025.1.**

| | |
|---|---|
| **Question** | What does oslo.messaging do with existing classic queues when the services restart with `rabbit_quorum_queue = true`? |
| **Why it matters** | [F17](../reference/findings.md#f17): in 2025.1 quorum queues are the only choice, `om_enable_rabbitmq_quorum_queues` and `om_enable_rabbitmq_high_availability` are gone, and `prechecks` fails on any queue that is not a quorum queue (except `reply_` and `_fanout` ones), on non-quorum `reply_` queues and on `_fanout` queues that are not streams (`roles/rabbitmq/tasks/precheck.yml:110-163`) [CODE]. A cloud still on classic queues must migrate before the 2025.1 run that passes the prechecks ([RabbitMQ](../components/rabbitmq.md#impact-and-risk)) |
| **Status** | [NOT AVAILABLE] oslo.messaging is not in these sources; nor is how long a manual migration takes |

<a id="q17"></a>

### Q17 — Real order of the staged etcd restarts

**From 2024.1.**

| | |
|---|---|
| **Question** | In which order do the etcd members really restart, on `upgrade` and outside it, and do etcd clients fail meanwhile? |
| **Why it matters** | The etcd play has no `serial` (`site.yml:485-496`), so `kolla_serial` does not batch it; quorum depends on the order of the handler restarts ([Controlled batches §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure), [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)) |
| **Status** | **Handlers answered from the source** [CODE], unchanged in 2025.1. The handlers look up the leader (`roles/etcd/handlers/main.yml:9-15`); outside `upgrade` and `config` they restart the non-leaders in a loop over the four values of `groups.etcd.index(host) % 4` (`:38-52`), then the leader, whose handler is defined last (`:54-61`). On `upgrade` the non-leader handler loops over `groups.etcd` without using `item` (`:27-34`), so each non-leader includes the restart tasks once per etcd member. Each restart waits for the client port and for `etcdctl endpoint health` (`roles/etcd/tasks/restart_services.yml:16-41`). [NOT AVAILABLE] How ansible-core orders, across hosts, the files included by one looped handler, so whether the `% 4` waves really restart one after another and whether the `upgrade` restarts are really one by one; whether etcd clients fail while the members restart |

<a id="q18"></a>

### Q18 — Which step creates the Keystone `service` role

**From 2024.1.**

| | |
|---|---|
| **Question** | Which step creates the Keystone `service` role that the roles grant to their users? |
| **Why it matters** | The nova role grants `service` to `nova` without creating it (`roles/nova/tasks/register.yml:2-8`); `service-ks-register` creates only the roles of its users plus `service_ks_register_roles`, empty by default (`roles/service-ks-register/tasks/main.yml:89-99`, `roles/service-ks-register/defaults/main.yml:29`) [CODE] ([Nova deep dive §2.1](../components/nova-deep-dive.md#21-installation-deploy-time-dependencies)) |
| **Status** | [NOT AVAILABLE] No Kolla-Ansible task found passes it, and the Keystone sources, where its own bootstrap is defined, are not part of this study |

<a id="q19"></a>

### Q19 — Containers of removed services left on hosts

**From 2024.1.**

| | |
|---|---|
| **Question** | What happens to a container of a service that Kolla-Ansible no longer deploys, left on a host by an earlier release: `chrony`, the services removed in 2024.1, and, new in 2025.1, the Swift containers and `neutron_linuxbridge_agent`? |
| **Why it matters** | 2025.1 has no `swift` or `chrony` role, and the linuxbridge agent is gone from the neutron services (`roles/neutron/defaults/main.yml`); the only `chrony` reference is the precheck that looks for an active host time daemon (`roles/prechecks/tasks/timesync_checks.yml:1-47`) [CODE]. So no tagged run stops, removes or checks those containers ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row "removed services") |
| **Status** | [NOT AVAILABLE] What such a container does on a host, for example Swift storage containers still serving after the upgrade |

<a id="q20"></a>

### Q20 — What else drifts on the first 2025.1 run of a 2024.1 cloud

**Re-asked for 2025.1.**

| | |
|---|---|
| **Question** | Besides the unit and `ulimits` changes of [F16](../reference/findings.md#f16), what makes containers differ on the first 2025.1 `deploy`, `reconfigure` or `deploy-containers` of a cloud deployed by 2024.1, for a container that the upgrade did not recreate? |
| **Why it matters** | [F16](../reference/findings.md#f16): the unit text and, with Docker outside the Red Hat family, the default `ulimits` changed, and both are compared [CODE]. Other definitions changed too: the DHCP and L3 agents gain `KOLLA_IMAGE`, `KOLLA_NAME` and `KOLLA_NEUTRON_WRAPPERS` and a `cgroupns_mode` (`roles/neutron/defaults/main.yml:55-89`), and the commands of `nova_libvirt`, the Open vSwitch containers, `mariadb_clustercheck` and `fluentd` changed, which `--check` now reports ([Kolla images §3.1](../concepts/kolla-images.md#31-what-is-compared)) [CODE] |
| **Status** | [NOT AVAILABLE] Which containers a real upgrade leaves for that first run, and whether the new commands work with an image that the upgrade did not replace (the `nova_libvirt_script_check` one-shot guards only the nova-libvirt case) |

<a id="q21"></a>

### Q21 — RabbitMQ version before the upgrade, and the step to 4.0

**Re-asked for 2025.1.**

| | |
|---|---|
| **Question** | Which RabbitMQ version does a cloud run before its first 2025.1 run, and does the version check let it through? |
| **Why it matters** | `upgrade` runs the version check first (`roles/rabbitmq/tasks/upgrade.yml:2`), which fails unless the running version is at most one minor version behind the target, or the step is 3.13 to 4.0 or 4.1, and names the `rabbitmq-upgrade` step to run first (`roles/rabbitmq/tasks/version-check.yml:45-65`) [CODE]. The 2025.1 `rabbitmq` image pins RabbitMQ 4.0 (kolla `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:2`), the 2024.1 one pinned 3.13, and kolla 2025.1 also has a `rabbitmq-4-1` image [CODE] ([RabbitMQ](../components/rabbitmq.md#before-and-after-a-run)) |
| **Status** | [NOT AVAILABLE] The running version is a property of each cloud, and the registry content is not in these sources |

<a id="q22"></a>

### Q22 — Guest console logging across a `nova_libvirt` restart

**New in 2025.1.**

| | |
|---|---|
| **Question** | When `nova_libvirt` restarts or is recreated, what happens to the console output of the running guests, now that it goes through a virtlogd that runs in that container? |
| **Why it matters** | `qemu.conf` sets `stdio_handler = "logd"` (2024.1: `"file"`), and `kolla_nova_libvirt_start` starts `virtlogd` in the background before `libvirtd` (`roles/nova-cell/templates/qemu.conf.j2:1`, kolla `docker/nova/nova-libvirt/kolla_nova_libvirt_start.sh:9,12`) [CODE]. A restart stops virtlogd while the guests keep running ([Kolla images §5.1](../concepts/kolla-images.md#51-nova-libvirt-the-start-path-is-passive), [§6](../concepts/kolla-images.md#6-day-2-consequences) item 20) |
| **Status** | [NOT AVAILABLE] libvirt, QEMU and virtlogd are not in these sources. Lab test: restart `nova_libvirt` with a running guest and check its console log and its state |

<a id="q23"></a>

### Q23 — Does a dropped `config.json` entry restart a container on every run?

**New in 2025.1.**

| | |
|---|---|
| **Question** | After an entry is removed from a service's `config.json`, does every later `deploy`, `reconfigure` or `deploy-containers` really restart that container until it is recreated, and is removing the container a safe way out? |
| **Why it matters** | [F21](../reference/findings.md#f21): `--check` raises `StateMismatch` for a recorded destination that is no longer listed, and the defaults state that records it is never pruned (kolla `docker/base/set_configs.py:476-537,589-642`) [CODE]; a run of these functions outside a container behaves that way |
| **Status** | [NOT AVAILABLE] No real container was run. Lab test: turn off `libvirt_enable_sasl` on one compute and run `reconfigure` twice ([Kolla images, Lab tests](../concepts/kolla-images.md#lab-tests)) |

## Related

- [What is not known](what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic, with the sections that mark
  each point
- [Risk register](../risk/risk-register.md) — the risks that the "Why it matters" rows cite
- [Findings](../reference/findings.md) — the findings that the questions cite:
  [F1](../reference/findings.md#f1), [F2](../reference/findings.md#f2), [F5](../reference/findings.md#f5),
  [F15](../reference/findings.md#f15), [F16](../reference/findings.md#f16), [F17](../reference/findings.md#f17),
  [F21](../reference/findings.md#f21) and [F22](../reference/findings.md#f22)
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — the answer
  to [Q14](#q14): what the one-shot containers run in each image
- [Compute scaling](../concepts/compute-scaling-and-performance.md) — the model that [Q7](#q7) and [Q8](#q8) concern
- [Limits of this study](../reference/method-and-limits.md#limits-of-this-study) — source code only, the Podman path
  read in the code only: why these questions cannot be settled here
- [Fact sheet E
  §14](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#14-register-of-open-questions-not-available-or-answered-from-code)
  — the register of open questions of fact sheet E
