---
title: Add a compute node
description: "The three limited commands that add a compute in 2025.1, what deploy --limit touches on the new host and on the others, and the /etc/hosts caveat."
tags: [nova, neutron, bootstrap-servers, pull, deploy, limit, facts, scaling]
---

# Add a compute node

How to add a compute node with `bootstrap-servers`, `pull` and `deploy`, each with `--limit` on the new host, and what
`deploy --limit` then touches: it creates the containers of the new compute, delegates tasks to a controller **and, new
in 2025.1, to the first existing compute**, gathers facts for all hosts, and needs the Nova API to answer. The sources
give no verification steps for the new compute beyond the one wait that `deploy` performs: see [§3](#3-verification).

The scenario section is written for the [assumed deployment](index.md#assumed-deployment), with `compute004` as the new
host.

> [!WARNING]
> Existing hosts' `/etc/hosts` is not updated (`bootstrap-servers --limit`), and a full `bootstrap-servers` run carries
> its own Docker-restart risk ([R14](../risk/risk-register.md#r14)) — see the caveats in [§2](#2-add-a-compute-node).

## 1. Commands

### 1.1 Add a compute node

```bash
kolla-ansible bootstrap-servers -i multinode --limit compute004
kolla-ansible pull -i multinode --limit compute004
kolla-ansible deploy -i multinode --limit compute004
```

Details in [§2](#2-add-a-compute-node).

- **Changed in 2025.1, the CLI:** `bootstrap-servers` is a command of the Python CLI; it runs `kolla-host.yml` with
  `kolla_action=bootstrap-servers` (`kolla_ansible/cli/commands.py:158-170`): facts first, then the
  `openstack.kolla.baremetal` role of ansible-collection-kolla on the `baremetal` hosts of the limit
  (`kolla-host.yml:1-14`). The role installs the engine named by `kolla_container_engine` (`docker` by default):
  `openstack.kolla.{{ container_engine }}`, then `openstack.kolla.{{ container_engine }}_sdk` (collection
  `roles/baremetal/tasks/install.yml:38`, `roles/baremetal/tasks/post-install.yml:7`,
  `roles/baremetal/defaults/main.yml:37`; kolla-ansible `group_vars/all.yml:100`). Use the engine of the rest of the
  deployment.
- Facts for **all** hosts are still gathered, sequentially from `compute004`: the second play of `gather-facts.yml`
  loops over `kolla_ansible_delegate_facts_hosts` (default `groups['all']`) with a delegated `setup`
  (`gather-facts.yml:34-62`, `group_vars/all.yml:43`; loop items run one after another, ansible-core 2.18.20
  `lib/ansible/executor/task_executor.py:299-336`). Enable fact caching for large inventories: with cached facts the
  delegated `setup` is skipped (`gather-facts.yml:60-61`).
- Discovery runs from the first compute of the batch, delegated to `nova-conductor[0]`
  (`roles/nova-cell/tasks/deploy.yml:21-40`, `roles/nova-cell/tasks/wait_discover_computes.yml:42-43, :87-90`,
  `roles/nova-cell/tasks/discover_computes.yml:21`). That host is outside the limit, but `delegate_to` works: Ansible
  looks the delegated host up in the whole inventory [CODE ansible-core 2.18.20 `lib/ansible/vars/manager.py:528-541`].
- `/etc/hosts` on existing hosts is **not** updated with the new compute (`bootstrap-servers` was limited). Still holds
  in 2025.1: the file is written by the `openstack.kolla.etc_hosts` role, imported first by `openstack.kolla.baremetal`
  and run on the play hosts only (collection `roles/baremetal/tasks/main.yml:2-3`, `roles/etc_hosts/tasks/main.yml:2-4`,
  `roles/etc_hosts/tasks/etc-hosts.yml:25-41`; `kolla-host.yml:4-14`). Live migration with `libvirt_tls`
  (hostname-based) and RabbitMQ name resolution may need a full `bootstrap-servers` run later ([fact sheet E
  §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).
- **Not batched differently:** `deploy` accepts `-e kolla_serial=N`, but with one host in the limit nothing changes
  ([F19](../reference/findings.md#f19) concerns `reconfigure` and `upgrade` only).

## 2. Add a compute node

[CODE] `deploy --limit compute004` (after `bootstrap-servers --limit` and `pull --limit`), read from the plays and
task files:

- **On compute004:** 10 containers created, one per `compare_container` item of a compute: fluentd, kolla_toolbox,
  cron (`common`), iscsid (with Cinder and its iSCSI backend), openvswitch_db, openvswitch_vswitchd,
  neutron_openvswitch_agent, nova_libvirt, nova_ssh, nova_compute (`roles/common/defaults/main.yml:3-32`;
  `roles/iscsi/defaults/main.yml:3-6, :62-67`, `group_vars/all.yml:911`, play `site.yml:454-467`;
  `roles/openvswitch/defaults/main.yml:3-35`; `roles/neutron/defaults/main.yml:30-53`;
  `roles/nova-cell/defaults/main.yml:5-23, :55-66`; groups in `inventory/multinode`). The count is the same as in
  2024.1 ([Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). The number of
  task results is [NOT AVAILABLE].
- **New in 2025.1, `compute_id`:** before the containers start, the nova-cell config step lists all hypervisors through
  `kolla_toolbox` on the first conductor. A new compute is not in that list, so the step writes
  `/etc/kolla/nova-compute/compute_id` with a UUID derived from the host's node name (`hypervisor_nodename | to_uuid`),
  and `config.json` copies it to `/var/lib/nova/compute_id` (`roles/nova-cell/tasks/config.yml:53-110`, generated at
  `:104-110`; `roles/nova-cell/templates/nova-compute.json.j2:10-15`). The UUID is a name-based `uuid5` [CODE
  ansible-core 2.18.20 `lib/ansible/plugins/filter/core.py:350-358`], so a new compute that reuses a former host's node
  name gets the same `compute_id`. [NOT AVAILABLE] What Nova does when that id still belongs to a deleted compute node
  record; to be confirmed by the community. The list call needs the Nova API: if it fails, the new compute fails
  ([F20](../reference/findings.md#f20)).
- **`hostnqn`, still holds:** the nova-cell config step writes `/etc/kolla/nova-compute/hostnqn`,
  `nqn.2014-08.org.nvmexpress:uuid:` followed by a UUID computed from `ansible_facts.hostname`
  (`roles/nova-cell/tasks/config.yml:248-257`, `roles/nova-cell/templates/hostnqn.j2:1`); `kolla_set_configs` copies it
  to `/etc/nvme/hostnqn` (`roles/nova-cell/templates/nova-compute.json.j2:65-70`). Whether a storage backend uses it is
  [NOT AVAILABLE].
- **New in 2025.1, the libvirt checks run on another compute:** the version and script checks start two one-shot
  containers from the `nova_libvirt` image, `run_once` and delegated to the first host of the `compute` group, an
  existing compute outside the limit, which must have the image or pull it
  (`roles/nova-cell/tasks/version-check.yml:2-21`, `roles/nova-cell/tasks/version-check.yml:79-98`). The current-version
  read runs only where a `nova_libvirt` container exists with another image, so not on compute004
  (`roles/nova-cell/tasks/version-check.yml:45-56`) ([F8](../reference/findings.md#f8)).
- **Order on the new host, changed in 2025.1:** the `openvswitch` play now runs before `nova.yml`, and the `neutron`
  play after it (`site.yml:605-619`, `site.yml:667`, `site.yml:669-691`). So on compute004 `openvswitch_db` and
  `openvswitch_vswitchd` exist before `nova_compute` starts, and `neutron_openvswitch_agent` only after the nova plays,
  including the registration wait, which only looks for the compute service in `openstack compute service list`
  (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`) ([F13](../reference/findings.md#f13), partly no longer
  holds). [NOT AVAILABLE] Whether instances can be scheduled on compute004 successfully before the neutron play finishes
  ([Execution flow
  §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)).
- **Elsewhere (via `delegate_to`):**
  - a Neutron bootstrap (DB sync) container on `control01` (`roles/neutron/tasks/bootstrap_service.yml:2-21`, imported
    by `roles/neutron/tasks/bootstrap.yml:38`; `neutron-server` is a child of `control`, `inventory/multinode:254-255`);
  - the hypervisor list above, through `kolla_toolbox` on `control01` (`roles/nova-cell/tasks/config.yml:59-73`);
  - `nova-manage cell_v2 list_cells` (one-shot `nova_list_cells` container) and `discover_hosts` (through
    `kolla_container_engine exec -t nova_conductor`) on `control01` (`roles/nova-cell/tasks/discover_computes.yml:4-23`,
    `roles/nova-cell/tasks/get_cell_settings.yml:2-21`; `nova-conductor` → `nova` → `control`,
    `inventory/multinode:99-100, :229-230`). A failure of this block stops every host of the play (`any_errors_fatal:
    true`, `roles/nova-cell/tasks/discover_computes.yml:23`);
  - `openstack compute service list` through `kolla_toolbox` on `control01`, retried up to 20 times every 10 s until
    the new compute's service is registered (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`, retries at
    `:27-28`);
  - the two libvirt check one-shots on the first compute, above.
- **Facts:** gathered for all 12 hosts (the 10 of the assumed deployment, compute004 and the `localhost` of
  `[deployment]`, `inventory/multinode:32-33`). The new compute itself runs the delegated `setup` loop sequentially
  (`gather-facts.yml:34-62`).
- **Not touched:** existing computes get no config writes or restarts; the first one runs the two one-shot containers,
  and all of them get the delegated `setup`. Controllers get no config writes or restarts, only delegated tasks: those
  listed above, the fact gathering (`setup` on all three controllers), and the Neutron DB and DB-user tasks (`mysql_db`,
  `mysql_user` run through `kolla_toolbox`) on `control01` (`roles/neutron/tasks/bootstrap.yml:2-36`). The Nova plays
  that target controllers (API and cell DB bootstrap, the `nova` role, the scheduler cell-cache refresh) have no host in
  the limit, so they do not run (`nova.yml:29-33, :67-71, :103-109, :152-156`).
- **Run on compute004 but aimed at shared services:** the Neutron Keystone registration (`service-ks-register`) runs
  once, with no `delegate_to`, so through the `kolla_toolbox` of compute004 itself (`roles/neutron/tasks/deploy.yml:4`,
  `roles/neutron/tasks/register.yml:2-8`, `roles/service-ks-register/tasks/main.yml:2-129`, `run_once` at `:129`).
- **Caveats:**
  - Existing hosts' `/etc/hosts` is not updated (`bootstrap-servers --limit`).
  - With `libvirt_tls: true` (hostname-based migration), the other computes' `/etc/hosts` lacks the new host until a
    full `bootstrap-servers` run, which carries its own Docker-restart risk ([R14](../risk/risk-register.md#r14)): the
    collection `docker` role still notifies `Restart docker` from its config tasks (collection
    `roles/docker/tasks/config.yml:52-53, :147-148`, handler `roles/docker/handlers/main.yml:10-15`). The `podman`
    role has no handlers (its role directory holds only `defaults/` and `tasks/`). [NOT AVAILABLE] Whether live
    migration to the new compute fails meanwhile ([fact sheet E
    §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation)).
  - The Nova API must answer for the run to succeed on compute004 (hypervisor list, registration wait).

## 3. Verification

- **What the run itself checks** [CODE]: after the new compute's containers exist, `deploy` waits for the new compute's
  service to appear in `openstack compute service list`, run through `kolla_toolbox` on `control01` and retried up to
  20 times every 10 s (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`). Then the discovery block runs
  `nova-manage cell_v2 discover_hosts`, and a failure of that block stops every host of the play
  (`roles/nova-cell/tasks/discover_computes.yml:4-23`). This is all that this study establishes: the wait looks only
  for the compute service in the list ([§2](#2-add-a-compute-node), "Order on the new host").
- **What the study does not establish** [NOT AVAILABLE]: that the new compute service is up and enabled, that the host
  is mapped to a cell, that a resource provider exists, that the network agent is alive, that an instance can boot on
  the new host, and how a missing `/etc/hosts` entry would show on the existing hosts. No task of the plays read for
  this page checks them, and no run was used as evidence; to be confirmed by the community.

> [!NOTE]
> **Outside this study.** The Academy has a page that shows these checks on a lab, with the commands and the expected
> result of each: [Adding a compute node to a running Kolla-Ansible
> deployment](../../../deploy/operations/adding-a-compute-node/), step 6, "Verify, then test with an instance". It is a
> deployment pattern, status `draft`, written for 2026.1, not for 2025.1. It is a pointer, not evidence for 2025.1:
> check the commands against your own release. The case of a host not mapped to a cell is explained in [No valid host
> was found, although capacity exists](../../../runbooks/scheduling/no-valid-host-with-free-capacity/) (runbook,
> 2026.1).

## Related

- [Risk register](../risk/risk-register.md) — [R14](../risk/risk-register.md#r14) (`bootstrap-servers` re-run on a
  live host), which this page names, and [R23](../risk/risk-register.md#r23) (any run with `--limit` on a large
  inventory)
- [Nova](../components/nova.md) — service cards of the roles `nova` and `nova-cell`, what changed in 2025.1, and where
  to look
- [Technical findings](../reference/findings.md) — [F8](../reference/findings.md#f8) (`--limit` does not confine
  actions), [F13](../reference/findings.md#f13) (deploy order) and [F20](../reference/findings.md#f20) (`compute_id`)
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files) — work per
  compute host, read from the task files: the `compare_container` items of a compute (10, §2)
- [Execution flow
  §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences) —
  compute node deployment: what one compute host experiences
- [Fact sheet E §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation) — `/etc/hosts`
  generation
- [Reconfigure Nova §6](reconfigure-nova.md#6-operational-risks-and-verification) — the checks listed after a Nova
  run (`openstack compute service list`, `nova-manage cell_v2 list_hosts`); see [§3](#3-verification) for what this
  page establishes
