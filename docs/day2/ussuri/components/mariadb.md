---
title: MariaDB/Galera
description: Where the study covers MariaDB/Galera (role mariadb), from the backup and recovery commands to tag impact, risks, dependencies, known bugs and open points.
tags: [mariadb, mariadb-backup, mariadb-recovery, serial, inventory, risk, dependencies, bugs, unknowns]
---

# MariaDB/Galera

This page is the starting point for MariaDB/Galera, the `mariadb` role: the containers `mariadb` and
`mariadb_clustercheck`, on the control nodes of the example inventory, selected by the tag `mariadb`. The lists below
say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run
and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Database operations](../operations/database-operations.md), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)

### Impact and risk

- **What the tag executes (`mariadb`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `mariadb`
- **Risks:** [R9](../risk/risk-register.md#r9); `mariadb_recovery`: [R18](../risk/risk-register.md#r18)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)

### Evidence

- **Fact sheet:** [fact sheet B
  §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `mariadb`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.4](../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 3 (batch size): `ANSIBLE_SERIAL` covers
  `reconfigure`/`upgrade` and `-e kolla_serial=N` covers `deploy`; mariadb and rabbitmq ignore it.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`. Repeat after each batch.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 8 (rollback material): a MariaDB backup
  (`kolla-ansible mariadb_backup`).
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `mariadb`:
  safe on its own "only on a healthy, fully synced cluster"; prerequisite: every node `Synced`.
- [R9](../risk/risk-register.md#r9), precautions for a MariaDB config change or image change: check `wsrep_cluster_size`
  and `Synced` on all nodes before; take a backup (`mariadb_backup`); watch between waves.
- [R18](../risk/risk-register.md#r18), precautions for `mariadb_recovery`: only when the cluster is fully down; identify
  the node with the highest seqno manually first.
- [R22](../risk/risk-register.md#r22), inventory reordering (haproxy, mariadb, glance, nova-conductor, keystone groups):
  MariaDB restart waves and active backend move. Precautions: treat inventory order as configuration; never reorder
  casually.
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 4 (fail-fast guards): reconfigure aborts if the cluster is fully stopped (multi-node) or any alive node is not
  Synced. `kolla-ansible stop` stops every node at once, so the next deploy/reconfigure fails until `mariadb_recovery`
  is run.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `mariadb`: the restart waves have
  no `any_errors_fatal`; recovery stops healthy nodes; clustercheck started even when disabled. Status: [CODE]: a node
  that fails its WSREP wait marks only its own host failed, and the next wave still restarts its nodes
  ([R9](../risk/risk-register.md#r9)); whether the failed node is then still joining, and how large the quorum and
  availability risk is, [NOT AVAILABLE].
- [Q6](../troubleshooting/open-questions.md#q6): "MariaDB rolling restart under load with a failure in wave 1: do later
  waves proceed?" Status: control flow answered from the source [CODE]: a node that fails its WSREP wait marks only its
  own host failed, and the next wave still restarts its nodes. [NOT AVAILABLE] Whether the failed node is then still
  joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and availability
  risk is.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "MariaDB": the sources do not establish whether node 0's restart wave runs first; after a failed WSREP wait (the next
  wave still restarts its nodes [CODE], [R9](../risk/risk-register.md#r9)), whether the failed node is then still
  joining, whether that can leave a single Synced node acting as donor, and how large the quorum and availability risk
  is; nor whether the DB containers come back as a non-primary cluster after a full stop, and whether a manual start
  left with `--wsrep-new-cluster` bootstraps a new cluster.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish dumb-init signal forwarding for `mysqld_safe` under the MariaDB image's own entrypoint,
  whether xtrace writes one-shot secrets (the MariaDB root password among them) to the container's stderr, or the cost
  of the recursive chown on large trees (the MariaDB datadir among them).
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", eleven items: reconfigure with a galera.cnf change;
  clustercheck restart is not rolling; WSREP-sync wait is only about 60 s; fail-fast guards; recovery takes the whole
  cluster down; recovery bug; recovery assumptions; upgrade; backup; credentials on the command line; scale-out restarts
  the whole cluster.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 10 and 16: recursive chown on data volumes
  at every start, the MariaDB datadir among them [CODE]; MariaDB has no automatic Galera recovery.
- [R20](../risk/risk-register.md#r20): a Glance reconfigure or deploy toggles the global MariaDB
  `log_bin_trust_function_creators` 1→0 around db sync.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py mariadb -->

| Item | Value |
|---|---|
| Play | site.yml:471 |
| Tags | mariadb |
| Play host patterns | mariadb |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `mariadb`, `mariadb_clustercheck` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers → register → check |
| Task files | backup.yml, bootstrap.yml, bootstrap_cluster.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, lookup_cluster.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, recover_cluster.yml, register.yml, restart_services.yml, stop.yml, upgrade.yml, wait_for_loadbalancer.yml |
| Templates | `backup.my.cnf.j2`, `galera.cnf.j2`, `mariabackup.json.j2`, `mariadb-clustercheck.json.j2`, `mariadb.json.j2`, `wsrep-notify.sh.j2`, `xinetd-clustercheck.j2` |
| Handlers (definition order) | Starting first MariaDB container; Wait for first MariaDB service port liveness; Wait for first MariaDB service to sync WSREP; Creating haproxy mysql user; Restart MariaDB on existing cluster members; Start MariaDB on new nodes; Ensure MariaDB is running normally on bootstrap host; Restart mariadb-clustercheck container |
| Key variables | `enable_mariadb`, `mariadb_*`, `database_address`, `enable_external_mariadb_load_balancer` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Database operations](../operations/database-operations.md) — the `mariadb_backup` and `mariadb_recovery` command
  lines
- [Change control-plane membership](../operations/change-control-plane-membership.md) — Galera membership changes
  restart all DB nodes
- [Stop and destroy](../operations/stop-and-destroy.md) — after `kolla-ansible stop`, MariaDB needs `mariadb_recovery`
- [HAProxy + Keepalived](haproxy-keepalived.md) — the database is reached through the internal VIP and HAProxy
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
