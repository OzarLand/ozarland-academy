---
title: MariaDB/Galera
description: Where the study covers MariaDB/Galera (role mariadb), from the backup and recovery commands to tag impact, risks, dependencies, known bugs and open points.
tags: [mariadb, mariadb-backup, mariadb-recovery, serial, inventory, risk, dependencies, bugs, unknowns]
---

# MariaDB/Galera

This page is the starting point for MariaDB/Galera, the `mariadb` role: the containers `mariadb` and
`mariadb_clustercheck` (the latter only with `enable_mariadb_clustercheck`, default `{{ enable_haproxy }}`,
`roles/mariadb/defaults/main.yml:45,132`), on the control nodes of the example inventory (`inventory/multinode:89-90`),
selected by the tag `mariadb`. The role is not applied by a play of `site.yml` itself: `site.yml:385` imports
`mariadb.yml`, whose five plays all carry the tag `mariadb`: apply the role (no `serial`), restart the hosts the
handlers put in `mariadb_restart`, start those in `mariadb_start` (both `serial: "33%"`), restart the bootstrap host,
then post-configuration (`mariadb.yml:3-72`) [CODE]. The service card below summarises these plays. The lists below
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
  and `Synced` on all nodes before; take a backup (`mariadb_backup`); watch between batches.
- [R18](../risk/risk-register.md#r18), precautions for `mariadb_recovery`: only when the cluster is fully down; identify
  the node with the highest seqno manually first.
- [R22](../risk/risk-register.md#r22), inventory reordering (loadbalancer, mariadb, glance, nova-conductor, keystone
  groups): the single active MariaDB HAProxy backend moves, because it is the first host of the default shard
  (`roles/mariadb/defaults/main.yml:64`). Precautions: treat inventory order as configuration; never reorder
  casually.
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 4 (fail-fast guards): reconfigure aborts if the cluster is fully stopped (multi-node) or any alive node is not
  Synced. `kolla-ansible stop` stops every node at once, so the next deploy/reconfigure fails until `mariadb_recovery`
  is run.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `mariadb`: the restart batches
  have no `any_errors_fatal`; recovery stops healthy nodes; clustercheck started even when disabled. Status in 2023.1
  [CODE]: the restart plays set neither `any_errors_fatal` nor `max_fail_percentage` (`mariadb.yml:14-40`). A node that
  fails its port or WSREP wait (`roles/mariadb/tasks/restart_services.yml:18-45`) marks only its own host failed; when
  that is every host of the batch (always so with three nodes, one host per batch), ansible-core ends the playbook and
  the later batches are not restarted; when the batch has other hosts that succeed, the next batch still restarts its
  nodes (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:204-208`, `lib/ansible/utils/helpers.py:25-32`;
  [R9](../risk/risk-register.md#r9)). Clustercheck: in deploy and reconfigure, the config and check tasks notify
  `restart mariadb-clustercheck` only for enabled items (`roles/mariadb/tasks/config.yml:42-53`,
  `check-containers.yml:13-18`); only recovery still starts it when disabled (`recover_cluster.yml:171-185,202-216`
  loop over `mariadb_services` with no `enabled` check). Whether the failed node is then still joining, and how large
  the quorum and availability risk is, [NOT AVAILABLE].
- [Q6](../troubleshooting/open-questions.md#q6): "MariaDB rolling restart under load with a failure in wave 1: do later
  waves proceed?" Status in 2023.1: control flow answered from the source [CODE], as in the row above: a failed batch
  ends the playbook; a batch with a partial failure lets the next batch restart its nodes. [NOT AVAILABLE] Whether the
  failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the
  quorum and availability risk is.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "MariaDB": the sources do not establish in which order `group_by` places the hosts in `mariadb_restart`, hence in
  which batch node 0 (the active HAProxy backend) restarts ([R9](../risk/risk-register.md#r9)); after a failed WSREP
  wait in a batch that does not stop the run, whether the failed node is then still joining, whether that can leave a
  single Synced node acting as donor, and how large the quorum and availability risk is; nor whether the DB containers
  come back as a non-primary cluster after a full stop, and whether a manual start left with `--wsrep-new-cluster`
  bootstraps a new cluster.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish dumb-init signal forwarding for `mysqld_safe` under the MariaDB image's own entrypoint,
  whether xtrace writes one-shot secrets (the MariaDB root password among them) to the container's stderr, or the cost
  of the recursive chown on large trees (the MariaDB datadir among them).
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", eleven items. Checked against 2023.1 [CODE]: reconfigure with
  a galera.cnf change (now restarted by the `mariadb.yml` restart plays in `serial: "33%"` batches, not by the
  handlers, `roles/mariadb/handlers/main.yml:56-73`); clustercheck restart is not rolling (the handler runs in the role
  play, on all notified hosts at once, `handlers/main.yml:75-91`); WSREP-sync wait is only about 60 s (10 × 6 s,
  `tasks/restart_services.yml:31-45`); fail-fast guards (`tasks/lookup_cluster.yml:35-42,72-78`); recovery takes the
  whole cluster down (`recover_cluster.yml:18-24`); recovery bug (clustercheck started when disabled,
  `recover_cluster.yml:171-185,202-216`); recovery assumptions (Docker volume path and fixed `/tmp` files,
  `recover_cluster.yml:44-60`); upgrade (`upgrade_mariadb` now runs in the post-configuration play, which has no
  `serial`, so on all nodes at once, `mariadb.yml:54-72`, `tasks/post-upgrade.yml:2-24`); backup (client pointed at
  `database_address`, `templates/backup.my.cnf.j2:5`; run on the first shard host, `defaults/main.yml:123`);
  credentials on the command line (`mysql -uroot -p{{ database_password }}`, `tasks/restart_services.yml:33-38`,
  `recover_cluster.yml:148`); scale-out restarts the whole cluster, batch by batch (`wsrep_cluster_address` lists every
  shard host, `templates/galera.cnf.j2:29`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 10 and 16: recursive chown on data volumes
  at every start, the MariaDB datadir among them [CODE]; MariaDB has no automatic Galera recovery.
- [R20](../risk/risk-register.md#r20): a Glance reconfigure or deploy toggles the global MariaDB
  `log_bin_trust_function_creators` 1→0 around db sync.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py mariadb -->

| Item | Value |
|---|---|
| Play | mariadb.yml (`import_playbook` at site.yml:385; 5 plays) |
| Tags | mariadb |
| Play host patterns | mariadb, mariadb_restart, mariadb_start, mariadb_bootstrap_restart |
| Node types in play (example inventory) | control |
| Node types running its containers | – |
| Containers | `mariadb`, `mariadb_clustercheck` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap |
| Task files | backup.yml, bootstrap.yml, bootstrap_cluster.yml, check-containers.yml, check.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, lookup_cluster.yml, main.yml, post-deploy.yml, post-upgrade.yml, precheck.yml, pull.yml, reconfigure.yml, recover_cluster.yml, register.yml, restart_services.yml, stop.yml, upgrade.yml |
| Templates | `backup.my.cnf.j2`, `galera.cnf.j2`, `hostname.j2`, `mariabackup.json.j2`, `mariadb-clustercheck.json.j2`, `mariadb.json.j2` |
| Handlers (definition order) | Starting first MariaDB container; Wait for first MariaDB service port liveness; Wait for first MariaDB service to sync WSREP; Ensure MariaDB is running normally on bootstrap host; Restart MariaDB on existing cluster members; Start MariaDB on new nodes; Restart mariadb-clustercheck container |
| Key variables | `enable_mariadb`, `mariadb_*`, `database_address`, `enable_external_mariadb_load_balancer` |
| Role dependencies | none |

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
