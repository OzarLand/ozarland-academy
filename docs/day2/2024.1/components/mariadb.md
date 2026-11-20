---
title: MariaDB/Galera
description: Where the 2024.1 study covers MariaDB/Galera (role mariadb), from the backup and recovery commands to tag impact, risks, dependencies, bugs and open points.
tags: [mariadb, mariadb-backup, mariadb-recovery, serial, inventory, risk, dependencies, bugs, unknowns]
---

# MariaDB/Galera

This page is the starting point for MariaDB/Galera, the `mariadb` role: the containers `mariadb` and
`mariadb_clustercheck` (the latter only with `enable_mariadb_clustercheck`, default `{{ enable_haproxy }}`,
`roles/mariadb/defaults/main.yml:45` and `roles/mariadb/defaults/main.yml:132`), on the control nodes of the example
inventory (`inventory/multinode:87-88`), selected by the tag `mariadb`. The role is not applied by a play of `site.yml`
itself: `site.yml:400` imports `mariadb.yml`, whose five plays all carry the tag `mariadb`: apply the role (no
`serial`), restart the hosts the handlers put in `mariadb_restart`, start those in `mariadb_start` (both
`serial: "33%"`), restart the bootstrap host, then post-configuration (`mariadb.yml:3-92`) [CODE]. **New in 2024.1:**
each of the five plays sets `max_fail_percentage` (`mariadb.yml:8-11`, `mariadb.yml:25-28`, `mariadb.yml:43-46`,
`mariadb.yml:59-62`, `mariadb.yml:75-78`), which changes nothing unless the operator sets it ([Known limits and open
points](#known-limits-and-open-points)). The service card below summarises these plays. The lists below say where the
study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what
stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Database operations](../operations/database-operations.md), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **Batches and failures:** [Write config first, apply in controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage): what
  `max_fail_percentage` does to the MariaDB restart plays

### Impact and risk

- **What the tag executes (`mariadb`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `mariadb`
- **Risks:** [R9](../risk/risk-register.md#r9); `mariadb_recovery`: [R18](../risk/risk-register.md#r18)
- **After an upgrade from 2023.1:** [F16](../reference/findings.md#f16): a MariaDB container that no 2024.1 run has
  recreated or restarted yet, and whose systemd unit 2023.1 wrote, is reported as changed by its first 2024.1 check
  (`roles/mariadb/tasks/check-containers.yml:2-18`); the handler then puts its host in `mariadb_restart`
  (`roles/mariadb/handlers/main.yml:56-63`), so it restarts in the `serial: "33%"` restart play
  (`mariadb.yml:18-34`) [CODE]

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Load balancer:** the `mariadb` include of the loadbalancer play (`site.yml:223-227`) configures HAProxy, or ProxySQL
  when `enable_proxysql` is set (default `no`, `group_vars/all.yml:839`): `loadbalancer-config` skips `haproxy-config`
  for the `mariadb` project when ProxySQL is enabled (`roles/loadbalancer-config/defaults/main.yml:2`,
  `roles/loadbalancer-config/tasks/main.yml:1-8`), and the loadbalancer role then removes the HAProxy `mariadb.cfg`
  (`roles/loadbalancer/tasks/config.yml:60-72`) [CODE]. **Still holds in 2024.1.** ProxySQL gets one writer per shard
  (`max_writers: 1`), with weight 100 for the first host of the shard and 10 for the others
  (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:23-56`) [CODE]; which node ProxySQL actually writes to is
  [NOT AVAILABLE]. **Changed in 2024.1:** the backend port in that file is `mariadb_port`, no longer `database_port`
  (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:33`); both are 3306 unless overridden, since `mariadb_port`
  defaults to `database_port` (`group_vars/all.yml:85`, `group_vars/all.yml:467`) [CODE].

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
  `reconfigure`/`upgrade` (`tools/kolla-ansible:522`, `tools/kolla-ansible:531`) and `-e kolla_serial=N` covers
  `deploy`; mariadb ignores it: its role play has no `serial` and its restart plays use a fixed `serial: "33%"`
  (`mariadb.yml:3-16`, `mariadb.yml:24`, `mariadb.yml:42`) [CODE]. **Still holds in 2024.1.**
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`. Repeat after each batch.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 8 (rollback material): a MariaDB backup
  (`kolla-ansible mariadb_backup`), which needs `enable_mariabackup: yes` (default `no`, `group_vars/all.yml:804`;
  [Database operations](../operations/database-operations.md)).
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `mariadb`:
  safe on its own "only on a healthy, fully synced cluster"; prerequisite: every node `Synced`.
- [R9](../risk/risk-register.md#r9), precautions for a MariaDB config change or image change: check `wsrep_cluster_size`
  and `Synced` on all nodes before; take a backup (`mariadb_backup`); watch between batches.
- [R18](../risk/risk-register.md#r18), precautions for `mariadb_recovery`: only when the cluster is fully down; identify
  the node with the highest seqno manually first.
- [R22](../risk/risk-register.md#r22), inventory reordering (loadbalancer, mariadb, glance, nova-conductor, keystone
  groups): the single active MariaDB HAProxy backend moves, because it is the first host of the default shard and the
  others are written as `backup` (`roles/mariadb/defaults/main.yml:64`) [CODE]. Precautions: treat inventory order as
  configuration; never reorder casually.
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 4 (fail-fast guards): deploy and reconfigure abort if the cluster exists but no node answers on its port
  (multi-node), or if any node that answers is not `Synced` (`roles/mariadb/tasks/lookup_cluster.yml:35-42`,
  `roles/mariadb/tasks/lookup_cluster.yml:72-78`) [CODE]. `kolla-ansible stop` stops every node at once, so the next
  deploy/reconfigure fails until `mariadb_recovery` is run.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `mariadb`: the restart batches
  have no `any_errors_fatal`; recovery stops healthy nodes; clustercheck started even when disabled. Status in 2024.1
  [CODE]: **changed in 2024.1**, the restart plays now set `max_fail_percentage`, from `mariadb_max_fail_percentage`,
  then `kolla_max_fail_percentage`, then 100 (`mariadb.yml:25-28`, `mariadb.yml:43-46`); neither variable is defined in
  the 2024.1 tree (`etc/kolla/globals.yml:27-31` only shows `kolla_max_fail_percentage` commented out), so the value
  is 100. They still set no `any_errors_fatal` (`mariadb.yml:18-52`). With 100, ansible-core 2.16.20 never breaks the
  play on the percentage: it compares the failed hosts of the current batch with the batch size and breaks only above
  1.0 (`lib/ansible/plugins/strategy/linear.py:336-348`, `lib/ansible/executor/task_queue_manager.py:330-338`). So the
  2023.1 behaviour still holds by default: a node that fails its port or WSREP wait
  (`roles/mariadb/tasks/restart_services.yml:18-45`) marks only its own host failed; when that is every host of the
  batch (always so with three nodes, one host per batch, `lib/ansible/utils/helpers.py:25-32`), ansible-core ends the
  playbook and the later batches are not restarted (`lib/ansible/executor/playbook_executor.py:204-209`,
  `lib/ansible/executor/playbook_executor.py:219-220`); when the batch has other hosts that succeed, the next batch
  still restarts its nodes ([R9](../risk/risk-register.md#r9)). **New in 2024.1:** with
  `-e mariadb_max_fail_percentage=0` (or `kolla_max_fail_percentage`), the first failed node of a batch marks the
  rest of its batch failed and ends the run before the next batch, whatever the batch size
  (`lib/ansible/plugins/strategy/linear.py:340-348`, `lib/ansible/executor/playbook_executor.py:196-198`) [CODE].
  Clustercheck: in deploy and reconfigure, the config and check tasks notify `restart mariadb-clustercheck` only for
  enabled items (`roles/mariadb/tasks/config.yml:42-53`, `roles/mariadb/tasks/check-containers.yml:13-18`); only
  recovery still starts it when disabled (`roles/mariadb/tasks/recover_cluster.yml:172-186` and
  `roles/mariadb/tasks/recover_cluster.yml:203-217` loop over `mariadb_services` with no `enabled` check). **Still
  holds in 2024.1.** Whether the failed node is then still joining, and how large the quorum and availability risk
  is, [NOT AVAILABLE].
- [Q6](../troubleshooting/open-questions.md#q6): "MariaDB rolling restart under load with a failure in wave 1: do later
  waves proceed?" Status in 2024.1: control flow answered from the source [CODE], as in the row above: with the
  default `max_fail_percentage` of 100, a failed batch ends the playbook and a batch with a partial failure lets the
  next batch restart its nodes; a lower value ends the run at the first failed node. [NOT AVAILABLE] Whether the
  failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the
  quorum and availability risk is.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "MariaDB": the sources do not establish in which order `group_by` places the hosts in `mariadb_restart`
  (`roles/mariadb/handlers/main.yml:56-63`), hence in which batch node 0 (the active HAProxy backend) restarts
  ([R9](../risk/risk-register.md#r9)); after a failed WSREP wait in a batch that does not stop the run, whether the
  failed node is then still joining, whether that can leave a single Synced node acting as donor, and how large the
  quorum and availability risk is; nor whether the DB containers come back as a non-primary cluster after a full stop,
  and whether a manual start left with `--wsrep-new-cluster` bootstraps a new cluster.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish dumb-init signal forwarding for `mysqld_safe` under the MariaDB image's own entrypoint,
  whether xtrace writes one-shot secrets (the MariaDB root password among them) to the container's stderr, or the cost
  of the recursive chown on large trees (the MariaDB datadir among them).
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", eleven items. Checked against 2024.1 [CODE]:
  - reconfigure with a galera.cnf change: the handlers only sort hosts into `mariadb_restart` and `mariadb_start`
    (`roles/mariadb/handlers/main.yml:56-73`); the `mariadb.yml` restart plays restart them in `serial: "33%"`
    batches (`mariadb.yml:18-52`). **Still holds.**
  - clustercheck restart is not rolling: the handler runs in the role play, on all notified hosts at once
    (`roles/mariadb/handlers/main.yml:75-91`). **Still holds.**
  - WSREP-sync wait: 10 retries 6 s apart (`roles/mariadb/tasks/restart_services.yml:31-45`), skipped for a node that
    joins an existing cluster (`roles/mariadb/tasks/restart_services.yml:46-51`). **Still holds.**
  - fail-fast guards (`roles/mariadb/tasks/lookup_cluster.yml:35-42`, `roles/mariadb/tasks/lookup_cluster.yml:72-78`).
    **Still holds.**
  - recovery takes the whole cluster down: the stop task runs on every MariaDB host when no recovery host is given
    (`roles/mariadb/tasks/recover_cluster.yml:18-25`, `roles/mariadb/tasks/recover_cluster.yml:95-96`). **Still
    holds;** the stop now passes `common_options` (`roles/mariadb/tasks/recover_cluster.yml:24`).
  - recovery bug: clustercheck started when disabled (`roles/mariadb/tasks/recover_cluster.yml:172-186`,
    `roles/mariadb/tasks/recover_cluster.yml:203-217`). **Still holds.**
  - recovery assumptions: fixed `/tmp` files on the host (`roles/mariadb/tasks/recover_cluster.yml:45-62`) and on the
    Ansible control host (`roles/mariadb/tasks/recover_cluster.yml:7-16`, `roles/mariadb/defaults/main.yml:113`).
    **Changed in 2024.1:** the volume path is no longer the hard-coded Docker one: the log copy and `grastate.dat`
    use `container_engine_volumes_path` (`roles/mariadb/tasks/recover_cluster.yml:47`,
    `roles/mariadb/tasks/recover_cluster.yml:106`), the Docker or the Podman volume directory
    (`group_vars/all.yml:156-158`).
  - upgrade: `upgrade_mariadb` runs in the post-configuration play, which has no `serial`, so on all nodes at once
    (`mariadb.yml:70-92`, `roles/mariadb/tasks/post-upgrade.yml:2-24`). **Still holds.** **Changed in 2024.1:** the
    image now appends the `mysql_upgrade` output to `mariadb-upgrade.log` under `/var/log/kolla/mariadb` (kolla
    `docker/mariadb/mariadb-server/extend_start.sh:3`, kolla `docker/mariadb/mariadb-server/extend_start.sh:55`),
    that is in the `kolla_logs` volume (`roles/mariadb/defaults/main.yml:86`); `start.sh` runs with `pipefail`
    (kolla `docker/base/start.sh:3-4`), so a failed `mysql_upgrade` still fails the one-shot.
  - backup: client pointed at `database_address` (`roles/mariadb/templates/backup.my.cnf.j2:5`), run on the first
    shard host (`roles/mariadb/defaults/main.yml:123`). **Still holds.** **Changed in 2024.1:** the backup user's
    privileges and schema ([Database operations](../operations/database-operations.md)).
  - credentials on the command line: `mysql -uroot -p{{ database_password }}`
    (`roles/mariadb/tasks/restart_services.yml:33-38`, `roles/mariadb/tasks/recover_cluster.yml:149`). **Still
    holds.**
  - scale-out restarts the whole cluster, batch by batch: `wsrep_cluster_address` lists every shard host
    (`roles/mariadb/templates/galera.cnf.j2:29`), so every existing node's `galera.cnf` changes and notifies
    `restart mariadb` (`roles/mariadb/tasks/config.yml:67-83`). **Still holds.**
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 10 and 16: recursive chown on data volumes
  at every start, the MariaDB datadir among them [CODE]; MariaDB has no automatic Galera recovery.
- [R20](../risk/risk-register.md#r20): a Glance reconfigure or deploy toggles the global MariaDB
  `log_bin_trust_function_creators` 1→0 around db sync (`roles/glance/tasks/bootstrap_service.yml:2-54`) [CODE].
  **Still holds in 2024.1.**

### Changed in 2024.1

- **`max_fail_percentage` on every MariaDB play**, and on `mariadb_backup.yml` and `mariadb_recovery.yml` (default 100,
  no change in behaviour unless set) ([Known limits and open points](#known-limits-and-open-points)).
- **Module rename only in the restart path:** the handlers and `restart_services.yml` differ from 2023.1 only by
  `kolla_docker` → `kolla_container` (`roles/mariadb/handlers/main.yml:7`, `roles/mariadb/handlers/main.yml:80`,
  `roles/mariadb/tasks/restart_services.yml:7`) [CODE].
- **Recovery follows the container engine** for its volume paths, and the stop passes `common_options`
  (`roles/mariadb/tasks/recover_cluster.yml:24`, `roles/mariadb/tasks/recover_cluster.yml:47`,
  `roles/mariadb/tasks/recover_cluster.yml:106`) [CODE].
- **Mariabackup:** schema `mysql` instead of `PERCONA_SCHEMA`, no database created any more, new privileges
  (`roles/mariadb/defaults/main.yml:124`, `roles/mariadb/tasks/register.yml:36-72`) [CODE]; see [Database
  operations](../operations/database-operations.md).
- **Image side:** the `mysql_upgrade` log (kolla `docker/mariadb/mariadb-server/extend_start.sh:55`); two new scripts
  in the images, `kolla_mariadb_backup_replica.sh` (kolla `docker/mariadb/mariadb-server/Dockerfile.j2:42`) and
  `socat_wrapper` (kolla `docker/mariadb/mariadb-clustercheck/Dockerfile.j2:9`), that Kolla-Ansible 2024.1 does not
  use: the backup runs `kolla_mariadb_backup.sh` (`roles/mariadb/tasks/backup.yml:15`) and clustercheck runs `socat`
  directly (`roles/mariadb/templates/mariadb-clustercheck.json.j2:2`) [CODE]. The clustercheck script is fetched
  from version 10.9 instead of 10.6 (kolla `docker/mariadb/mariadb-base/Dockerfile.j2:27-31`) [CODE].
- **ProxySQL** backend port variable ([Dependencies](#dependencies)).

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py mariadb -->

| Item | Value |
|---|---|
| Play | mariadb.yml (`import_playbook` at site.yml:400; 5 plays) |
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
- [HAProxy + Keepalived](haproxy-keepalived.md) — the database is reached through the internal VIP and HAProxy, or
  ProxySQL
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `serial` and
  `max_fail_percentage` across plays
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
