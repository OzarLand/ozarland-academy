---
title: Add a compute node
description: The three limited commands that add a compute, what deploy --limit touches on the new host and on the others, and the caveats about /etc/hosts.
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

- Facts for **all** hosts are still gathered, sequentially from `compute501` (`gather-facts.yml:29-50`; loop items
  run one after another, ansible 2.9.27 `lib/ansible/executor/task_executor.py:317-367`). Enable fact caching for
  large inventories.
- Discovery runs from the first compute of the batch, delegated to `nova-conductor[0]`. That host is outside the
  limit, but `delegate_to` works: Ansible looks the delegated host up in the whole inventory [CODE ansible 2.9.27
  `lib/ansible/vars/manager.py:569-594`, `lib/ansible/inventory/manager.py:189-190`].
- `/etc/hosts` on existing hosts is **not** updated with the new compute (`bootstrap-servers` was limited). Live
  migration with `libvirt_tls` (hostname-based) and RabbitMQ name resolution may need a full `bootstrap-servers` run
  later ([fact sheet E §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).

## 2. Add a compute node

[CODE] `deploy --limit compute004` (after `bootstrap-servers --limit` and `pull --limit`), read from the plays and
task files:

- **On compute004:** 11 containers created, one per `compare_container` item of a compute ([Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). The number of
  task results is [NOT AVAILABLE].
- **Elsewhere (via `delegate_to`):**
  - a Neutron bootstrap (DB sync) container on `control01` (`roles/neutron/tasks/bootstrap_service.yml:19-22`);
  - `nova-manage cell_v2 list_cells` and `discover_hosts` on `control01`
    (`roles/nova-cell/tasks/discover_computes.yml:4-21`, `get_cell_settings.yml:2-20`);
  - a Keystone API call to wait for compute registration (`roles/nova-cell/tasks/wait_discover_computes.yml:8-42`).
- **Facts:** gathered for all 12 hosts. The new compute itself runs the delegated `setup` loop sequentially
  (`gather-facts.yml:29-50`).
- **Not touched:** existing computes, apart from the delegated `setup` above. Controllers get no config writes or
  restarts, only delegated tasks: those listed above, the fact gathering above (`setup` on all three controllers), and
  the Neutron DB and DB-user tasks (`mysql_db`, `mysql_user` run through `kolla_toolbox`) on `control01`.
- **Caveats:**
  - Existing hosts' `/etc/hosts` is not updated (`bootstrap-servers --limit`).
  - With `libvirt_tls: true` (hostname-based migration), the other computes' `/etc/hosts` lacks the new host until a
    full `bootstrap-servers` run, which carries its own Docker-restart risk ([R14](../risk/risk-register.md#r14)).
    [NOT AVAILABLE] Whether live migration to it fails meanwhile ([fact sheet E
    §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).

## Related

- [Risk register](../risk/risk-register.md) — [R14](../risk/risk-register.md#r14) (`bootstrap-servers` re-run on a
  live host), which this page names, and [R23](../risk/risk-register.md#r23) (any run with `--limit` on a large
  inventory)
- [Nova](../components/nova.md) — service cards of the roles `nova` and `nova-cell`, and where to look
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files) — work per
  compute host, read from the task files: the 11 `compare_container` items of a compute
- [Execution flow
  §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences) —
  compute node deployment: what one compute host experiences
- [Fact sheet E §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation) — `/etc/hosts`
  generation
- [Reconfigure Nova §6](reconfigure-nova.md#6-operational-risks-and-verification) — the checks listed after a Nova
  run (`openstack compute service list`, `nova-manage cell_v2 list_hosts`); this page lists none
