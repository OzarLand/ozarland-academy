---
title: Add a compute node
description: The three limited commands that add a compute in 2024.1, what deploy --limit touches on the new host and on the others, and the /etc/hosts caveat.
tags: [nova, neutron, bootstrap-servers, pull, deploy, limit, facts, scaling]
---

# Add a compute node

How to add a compute node with `bootstrap-servers`, `pull` and `deploy`, each with `--limit` on the new host, and what
`deploy --limit` then touches: it creates the containers of the new compute, delegates tasks to the controllers, gathers
facts for all hosts, and does not touch existing computes apart from the delegated `setup`. The page gives no
verification steps for the new compute.

The scenario section is written for the [assumed deployment](index.md#assumed-deployment), with `compute004` as the new
host.

> [!WARNING]
> Existing hosts' `/etc/hosts` is not updated (`bootstrap-servers --limit`), and a full `bootstrap-servers` run carries
> its own Docker-restart risk ([R14](../risk/risk-register.md#r14)) — see the caveats in [§2](#2-add-a-compute-node).

## 1. Commands

### 1.1 Add a compute node

```bash
kolla-ansible -i multinode bootstrap-servers --limit compute501
kolla-ansible -i multinode pull --limit compute501
kolla-ansible -i multinode deploy --limit compute501
```

Details in [§2](#2-add-a-compute-node).

- `bootstrap-servers` runs `ansible/kolla-host.yml` (`tools/kolla-ansible:485-488`): facts first, then the
  `openstack.kolla.baremetal` role of ansible-collection-kolla on the `baremetal` hosts of the limit
  (`kolla-host.yml:2-14`). **Changed in 2024.1:** the container engine it installs is no longer always Docker. The role
  imports `openstack.kolla.{{ container_engine }}` and then `openstack.kolla.{{ container_engine }}_sdk` (collection
  `roles/baremetal/tasks/install.yml:37-38`, `roles/baremetal/tasks/post-install.yml:6-7`), with `container_engine`
  taken from `kolla_container_engine`, `docker` by default (collection `roles/baremetal/defaults/main.yml:37`;
  kolla-ansible `group_vars/all.yml:92`). So the new compute gets the `docker` and `docker_sdk` roles, or, with
  `kolla_container_engine: podman`, the `podman` and `podman_sdk` roles, which are new in the 2024.1 collection.
  Use the engine of the rest of the deployment: every `kolla_container` task of `deploy` passes the same variable
  (`group_vars/all.yml:142-153`, key at `:153`).
- Facts for **all** hosts are still gathered, sequentially from `compute501` (`gather-facts.yml:34-62`; loop items
  run one after another, ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:288-336`). Enable fact caching for
  large inventories: with cached facts the delegated `setup` is skipped (`gather-facts.yml:60-61`). New in 2024.1, both
  fact plays and the `baremetal` play set `max_fail_percentage`, 100 unless you set it (`gather-facts.yml:7-10, :36-39`,
  `kolla-host.yml:8-11`): with the default, nothing changes for a single new host.
- Discovery runs from the first compute of the batch, delegated to `nova-conductor[0]`
  (`roles/nova-cell/tasks/deploy.yml:19-37`, `roles/nova-cell/tasks/wait_discover_computes.yml:42-43, :87-90`,
  `roles/nova-cell/tasks/discover_computes.yml:21`). That host is outside the limit, but `delegate_to` works: Ansible
  looks the delegated host up in the whole inventory [CODE ansible-core 2.16.20 `lib/ansible/vars/manager.py:528-536`,
  `lib/ansible/inventory/manager.py:197-198`].
- `/etc/hosts` on existing hosts is **not** updated with the new compute (`bootstrap-servers` was limited). Still holds
  in 2024.1: the file is written by the `openstack.kolla.etc_hosts` role, imported first by `openstack.kolla.baremetal`
  and run on the play hosts only (collection `roles/baremetal/tasks/main.yml:2-3`, `roles/etc_hosts/tasks/main.yml:2-4`,
  `roles/etc_hosts/tasks/etc-hosts.yml:25-37`; `kolla-host.yml:4-14`). Live migration with `libvirt_tls`
  (hostname-based) and RabbitMQ name resolution may need a full `bootstrap-servers` run later ([fact sheet E
  §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).

## 2. Add a compute node

[CODE] `deploy --limit compute004` (after `bootstrap-servers --limit` and `pull --limit`), read from the plays and
task files:

- **On compute004:** 10 containers created, one per `compare_container` item of a compute: fluentd, kolla_toolbox,
  cron (`common`), iscsid (`enable_iscsid` follows the Cinder LVM backend), openvswitch_db, openvswitch_vswitchd,
  neutron_openvswitch_agent, nova_libvirt, nova_ssh, nova_compute (`roles/common/defaults/main.yml:3-32`;
  `roles/iscsi/defaults/main.yml:3-6, :62-67`, `group_vars/all.yml:753, :794`, play `site.yml:439-452`;
  `roles/openvswitch/defaults/main.yml:3-35`; `roles/neutron/defaults/main.yml:26-49`;
  `roles/nova-cell/defaults/main.yml:3-21, :53-64`; groups in `inventory/multinode`). The count is the same as in
  2023.1 ([Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). The number of
  task results is [NOT AVAILABLE].
- **New in 2024.1, `hostnqn`:** the nova-cell config step writes `/etc/kolla/nova-compute/hostnqn` on the compute,
  `nqn.2014-08.org.nvmexpress:uuid:` followed by a UUID computed from `ansible_facts.hostname`, and notifies the
  nova-compute restart (`roles/nova-cell/tasks/config.yml:203-216`, `roles/nova-cell/templates/hostnqn.j2:1`).
  `kolla_set_configs` copies it to `/etc/nvme/hostnqn` in the `nova_compute` container
  (`roles/nova-cell/templates/nova-compute.json.j2:59-64`). The UUID is a name-based `uuid5` of the hostname
  [CODE ansible-core 2.16.20 `lib/ansible/plugins/filter/core.py:346-354`], so it depends only on the hostname: a new
  compute that reuses a former host's hostname gets the same NQN. 2023.1 wrote no such file (no `hostnqn` in its
  `ansible/` tree). Whether a storage backend uses it is [NOT AVAILABLE].
- **Order on the new host:** `nova.yml` is imported before the `openvswitch` and `neutron` plays
  (`site.yml:609, :611-624, :671-693`). So on compute004 the `nova_compute` container is started, and its registration
  awaited, before `openvswitch_db`, `openvswitch_vswitchd` and `neutron_openvswitch_agent` exist. The wait only looks
  for the compute service in `openstack compute service list` (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`).
  Still holds in 2024.1. [NOT AVAILABLE] Whether instances can be scheduled on compute004 successfully before the
  later plays finish ([Execution flow
  §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)).
- **Elsewhere (via `delegate_to`):**
  - a Neutron bootstrap (DB sync) container on `control01` (`roles/neutron/tasks/bootstrap_service.yml:2-21`, imported
    by `roles/neutron/tasks/bootstrap.yml:38`; `neutron-server` is a child of `control`, `inventory/multinode:252-253`);
  - `nova-manage cell_v2 list_cells` (one-shot `nova_list_cells` container) and `discover_hosts` (through
    `kolla_container_engine exec -t nova_conductor`) on `control01` (`roles/nova-cell/tasks/discover_computes.yml:4-23`,
    `get_cell_settings.yml:2-21`; `nova-conductor` → `nova` → `control`, `inventory/multinode:99-100, :230-231`).
    Changed in 2024.1: the `exec` gets `-t` (`discover_computes.yml:17`). A failure of this block stops every host of
    the play (`any_errors_fatal: true`, `discover_computes.yml:23`);
  - `openstack compute service list` through `kolla_toolbox` on `control01`, retried up to 20 times every 10 s until
    the new compute's service is registered (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`).
- **Facts:** gathered for all 12 hosts (the 10 of the assumed deployment, compute004 and the `localhost` of
  `[deployment]`, `inventory/multinode:32-33`). The new compute itself runs the delegated `setup` loop sequentially
  (`gather-facts.yml:34-62`).
- **Not touched:** existing computes, apart from the delegated `setup` above. Controllers get no config writes or
  restarts, only delegated tasks: those listed above, the fact gathering above (`setup` on all three controllers), and
  the Neutron DB and DB-user tasks (`mysql_db`, `mysql_user` run through `kolla_toolbox`) on `control01`
  (`roles/neutron/tasks/bootstrap.yml:2-36`). The Nova plays that target controllers (API and cell DB bootstrap, the
  `nova` role, the scheduler cell-cache refresh) have no host in the limit, so they do not run (`nova.yml:29-33,
  :67-71, :103-109, :152-156`).
- **Run on compute004 but aimed at shared services:** the Neutron Keystone registration (`service-ks-register`) runs
  once, with no `delegate_to`, so through the `kolla_toolbox` of compute004 itself (`roles/neutron/tasks/deploy.yml:4`,
  `roles/neutron/tasks/register.yml:2-8`, `roles/service-ks-register/tasks/main.yml:2-126`, `run_once` at `:126`).
- **Caveats:**
  - Existing hosts' `/etc/hosts` is not updated (`bootstrap-servers --limit`).
  - With `libvirt_tls: true` (hostname-based migration), the other computes' `/etc/hosts` lacks the new host until a
    full `bootstrap-servers` run, which carries its own Docker-restart risk ([R14](../risk/risk-register.md#r14)): the
    collection `docker` role still notifies `Restart docker` from its config tasks (collection
    `roles/docker/tasks/config.yml:52-53, :113-114`, handler `roles/docker/handlers/main.yml:10-15`). The `podman`
    role has no handlers (its role directory holds only `defaults/` and `tasks/`). [NOT AVAILABLE] Whether live
    migration to the new compute fails meanwhile ([fact sheet E
    §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).

## Related

- [Risk register](../risk/risk-register.md) — [R14](../risk/risk-register.md#r14) (`bootstrap-servers` re-run on a
  live host), which this page names, and [R23](../risk/risk-register.md#r23) (any run with `--limit` on a large
  inventory)
- [Nova](../components/nova.md) — service cards of the roles `nova` and `nova-cell`, and where to look
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files) — work per
  compute host, read from the task files: the `compare_container` items of a compute (10 in 2024.1, §2)
- [Execution flow
  §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences) —
  compute node deployment: what one compute host experiences
- [Fact sheet E §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation) — `/etc/hosts`
  generation
- [Reconfigure Nova §6](reconfigure-nova.md#6-operational-risks-and-verification) — the checks listed after a Nova
  run (`openstack compute service list`, `nova-manage cell_v2 list_hosts`); this page lists none
