---
title: MariaDB/Galera
description: "The 2025.1 study of MariaDB/Galera: ProxySQL by default, the backup and recovery commands, tag impact, risks, dependencies, bugs and open points."
tags: [mariadb, mariadb-backup, mariadb-recovery, proxysql, serial, inventory, risk, dependencies, bugs, unknowns]
---

# MariaDB/Galera

This page is the starting point for MariaDB/Galera, the `mariadb` role: the container `mariadb` and, only with
`enable_mariadb_clustercheck`, the container `mariadb_clustercheck` (`roles/mariadb/defaults/main.yml:45`), on the
control nodes of the example inventory (`inventory/multinode:87-88`), selected by the tag `mariadb`. The role is not
applied by a play of `site.yml` itself: `site.yml:415` imports `mariadb.yml`, whose five plays all carry the tag
`mariadb`: apply the role (no `serial`), restart the hosts the handlers put in `mariadb_restart`, start those in
`mariadb_start` (both `serial: "33%"`), restart the bootstrap host, then post-configuration (`mariadb.yml:3-92`)
[CODE]. Each play sets `max_fail_percentage` (`mariadb.yml:8-11`, `:25-28`, `:43-46`, `:59-62`, `:75-78`), which changes
nothing unless the operator sets it ([Known limits and open points](#known-limits-and-open-points)).

**Changed in 2025.1** [CODE]:
- **ProxySQL is the default database load balancer** (`enable_proxysql: "yes"`, `group_vars/all.yml:958`; `"no"` in
  2024.1). `enable_mariadb_clustercheck` now defaults in the role to `'True' if mariadb_loadbalancer == 'haproxy' else
  'False'` (`roles/mariadb/defaults/main.yml:132`), so by default there is **no `mariadb_clustercheck` container**, and
  `upgrade` removes an existing one when ProxySQL is the load balancer (`roles/mariadb/tasks/upgrade.yml:2-9`).
- **Restarts:** no config task notifies; `check-containers.yml` imports `service-check-containers`, which notifies
  `Restart mariadb container` for a changed container (`roles/mariadb/tasks/check-containers.yml:2-3`); the handlers
  still only sort the hosts into the restart groups.
- **Checks and logins:** the WSREP waits and the post-deploy check use `kolla_toolbox mysql_query` against the node's own
  address, not `mysql` through the VIP (`roles/mariadb/tasks/restart_services.yml:31-53`,
  `roles/mariadb/tasks/check.yml:6-22`); `check.yml` also runs the `service-check` role of `kolla-ansible check`.
- **Configuration:** `galera.cnf` gains `innodb_log_file_size = 2048M` (`roles/mariadb/templates/galera.cnf.j2:61`;
  `group_vars/all.yml:564`) and the container command becomes `/usr/bin/mariadbd-safe`
  (`roles/mariadb/templates/mariadb.json.j2:3`); both make the first 2025.1 run restart every node, in batches.
- **Commands:** `kolla-ansible mariadb-backup` and `kolla-ansible mariadb-recovery`, with hyphens
  (`setup.cfg:72-73`); the backup now reads the backup host itself (`roles/mariadb/templates/backup.my.cnf.j2:5-6`).

The service card below summarises these plays. The lists below say where the study covers how to operate it, its
impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

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
- **Risks:** [R9](../risk/risk-register.md#r9); `mariadb-recovery`: [R18](../risk/risk-register.md#r18)
- **After an upgrade from 2024.1:** [F16](../reference/findings.md#f16): the unit template changed again, so the first
  2025.1 check of a MariaDB container reports it as changed (`roles/service-check-containers/tasks/main.yml:4-41`); the
  same run also sees the new `galera.cnf` and the new command (above). The handler then puts the host in
  `mariadb_restart` (`roles/mariadb/handlers/main.yml:59-65`), so it restarts in the `serial: "33%"` restart play
  (`mariadb.yml:18-34`) [CODE]. [NOT AVAILABLE] How long MariaDB takes to start with a changed redo log size, and the
  disk it then uses; to be confirmed by the community.
- **Switch from HAProxy to ProxySQL during the upgrade:** a 2024.1 cloud that kept the 2024.1 default (`enable_proxysql:
  "no"`) and does not set it in `globals.yml` moves to ProxySQL with its 2025.1 upgrade. The loadbalancer play renders
  and starts ProxySQL and removes the HAProxy `mariadb.cfg`
  ([fact sheet A, 1.4](../reference/factsheets/a-infra-lb-ovn.md#14-config-files-generated-ansibleroleshaproxytasksconfigyml)),
  then the mariadb play removes `mariadb_clustercheck` (`roles/mariadb/tasks/upgrade.yml:2-9`). The monitor user is
  created before ProxySQL starts, for this case (comment `roles/mariadb/tasks/loadbalancer.yml:10-16`, task `:18-40`)
  [CODE]. [NOT AVAILABLE] Whether client connections are cut during the switch; to be confirmed by the community.

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Load balancer:** the `mariadb` include of the loadbalancer play (`site.yml:223-227`) configures ProxySQL by default,
  or HAProxy: `loadbalancer-config` skips `haproxy-config` for the `mariadb` project when ProxySQL is enabled
  (`roles/loadbalancer-config/defaults/main.yml:2`, `roles/loadbalancer-config/tasks/main.yml:2-8`), and the
  loadbalancer role then removes the HAProxy `mariadb.cfg` (`roles/loadbalancer/tasks/config.yml:63-72`) [CODE].
  ProxySQL gets one writer per shard (`max_writers: 1`), with weight 100 for the first host of the shard and 10 for the
  others (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:77-110`) [CODE]; which node ProxySQL actually writes
  to is [NOT AVAILABLE]. The backend port is `mariadb_port` (`:87`), which defaults to `database_port`
  (`group_vars/all.yml:91,538`).
- **Users:** with ProxySQL the shard root user is `root_shard_<id>` and the backup user `backup_shard_<id>`
  (`roles/mariadb/defaults/main.yml:125,137`; `group_vars/all.yml:556-557`), and the monitor user is `monitor`
  (`group_vars/all.yml:545`) [CODE].

### Evidence

- **Fact sheet:** [fact sheet B
  §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `mariadb`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.4](../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 3 (batch size): **changed in 2025.1**,
  `reconfigure` and `upgrade` always pass `kolla_serial=0` (`kolla_ansible/cli/commands.py:22,136,278`;
  [F19](../reference/findings.md#f19)) and only `deploy -e kolla_serial=N` batches; mariadb ignores it anyway: its role
  play has no `serial` and its restart plays use a fixed `serial: "33%"` (`mariadb.yml:3-16`, `:24`, `:42`) [CODE].
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`. Repeat after each batch. **New in 2025.1:**
  `kolla-ansible check -t mariadb` fails when a MariaDB container is missing, stopped or `unhealthy`, then runs
  `SHOW DATABASES` on each node (`roles/mariadb/tasks/check.yml:1-22`); it does not test the VIP.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 8 (rollback material): a MariaDB backup
  (`kolla-ansible mariadb-backup`), which needs `enable_mariabackup: yes` (default `no`, `group_vars/all.yml:922`;
  [Database operations](../operations/database-operations.md)).
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `mariadb`:
  safe on its own "only on a healthy, fully synced cluster"; prerequisite: every node `Synced`.
- [R9](../risk/risk-register.md#r9), precautions for a MariaDB config change or image change: check `wsrep_cluster_size`
  and `Synced` on all nodes before; take a backup (`mariadb-backup`); watch between batches.
- [R18](../risk/risk-register.md#r18), precautions for `mariadb-recovery`: only when the cluster is fully down; identify
  the node with the highest seqno manually first.
- [R22](../risk/risk-register.md#r22), inventory reordering (loadbalancer, mariadb, glance, nova-conductor, keystone
  groups): the first host of the default shard is the preferred writer, weight 100 in ProxySQL
  (`roles/loadbalancer/templates/proxysql/proxysql.yaml.j2:80-84`) and the only active backend in HAProxy mode
  (`roles/mariadb/defaults/main.yml:64`) [CODE]. Precautions: treat inventory order as configuration; never reorder
  casually.
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 4 (fail-fast guards): deploy and reconfigure abort if the cluster exists but no node answers on its port
  (multi-node), or if any node that answers is not `Synced` (`roles/mariadb/tasks/lookup_cluster.yml:36-43`,
  `roles/mariadb/tasks/lookup_cluster.yml:73-79`) [CODE]. `kolla-ansible stop` stops every node at once, so the next
  deploy/reconfigure fails until `mariadb-recovery` is run.
- **New in 2025.1, `migrate-container-engine`:** that command redeploys with `migration_flag`, which makes the mariadb
  role run the recovery path, stopping every MariaDB container, before the bootstrap
  (`migrate-container-engine.yml:12-17`; `roles/mariadb/tasks/deploy.yml:6-9`) [CODE]. Plan it as a full database
  outage.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `mariadb`: the restart batches
  have no `any_errors_fatal`; recovery stops healthy nodes. Status in 2025.1 [CODE]: the restart plays set
  `max_fail_percentage`, from `mariadb_max_fail_percentage`, then `kolla_max_fail_percentage`, then 100
  (`mariadb.yml:25-28`, `:43-46`); neither variable is defined in the 2025.1 tree (`etc/kolla/globals.yml:29-31` only
  shows `kolla_max_fail_percentage` commented out), so the value is 100. They still set no `any_errors_fatal`
  (`mariadb.yml:18-52`). With 100, ansible-core 2.18.20 never breaks the play on the percentage: it compares the failed
  hosts of the current batch with the batch size and breaks only above 1.0
  (`lib/ansible/plugins/strategy/linear.py:335-347`, `lib/ansible/executor/task_queue_manager.py:322-334`). So a node
  that fails its port or WSREP wait (`roles/mariadb/tasks/restart_services.yml:18-47`) marks only its own host failed;
  when that is every host of the batch (always so with three nodes, one host per batch,
  `lib/ansible/utils/helpers.py:23-30`), ansible-core ends the playbook and the later batches are not restarted
  (`lib/ansible/executor/playbook_executor.py:198-204`); when the batch has other hosts that succeed, the next batch
  still restarts its nodes ([R9](../risk/risk-register.md#r9)). With `-e mariadb_max_fail_percentage=0` (or
  `kolla_max_fail_percentage`), the first failed node of a batch ends the run before the next batch, whatever the
  batch size (`lib/ansible/plugins/strategy/linear.py:339-347`, `lib/ansible/executor/playbook_executor.py:194-196`)
  [CODE]. **No longer holds in 2025.1:** "clustercheck started even when disabled": recovery now loops over the enabled,
  mapped services only (`roles/mariadb/tasks/recover_cluster.yml:186`, `:217`). Whether the failed node is then still
  joining, and how large the quorum and availability risk is, [NOT AVAILABLE].
- [Q6](../troubleshooting/open-questions.md#q6): "MariaDB rolling restart under load with a failure in wave 1: do later
  waves proceed?" Control flow answered from the source [CODE], as in the row above. [NOT AVAILABLE] Whether the
  failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large the
  quorum and availability risk is.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "MariaDB": the sources do not establish in which order `group_by` places the hosts in `mariadb_restart`
  (`roles/mariadb/handlers/main.yml:59-65`), hence in which batch node 0 restarts ([R9](../risk/risk-register.md#r9));
  how ProxySQL moves the writer while a node restarts; after a failed WSREP wait in a batch that does not stop the run,
  whether the failed node is then still joining; nor whether the DB containers come back as a non-primary cluster
  after a full stop. These points are to be confirmed by the community.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish dumb-init signal forwarding for `mariadbd-safe` under the MariaDB image's own
  entrypoint (kolla `docker/mariadb/mariadb-server/Dockerfile.j2:65-76`), whether xtrace writes one-shot secrets to the
  container's stderr, or the cost of the recursive chown on large trees (the MariaDB datadir among them).
- [fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities". Checked against 2025.1 [CODE]:
  - reconfigure with a galera.cnf change: the handlers only sort hosts into `mariadb_restart` and `mariadb_start`
    (`roles/mariadb/handlers/main.yml:59-74`); the `mariadb.yml` restart plays restart them in `serial: "33%"`
    batches (`mariadb.yml:18-52`). **Still holds.**
  - clustercheck restart is not rolling: the handler runs in the role play, on all notified hosts at once
    (`roles/mariadb/handlers/main.yml:76-90`). **Still holds, in HAProxy mode only.**
  - WSREP-sync wait: 10 retries 6 s apart (`roles/mariadb/tasks/restart_services.yml:31-47`), skipped for a node that
    joins an existing cluster (`:48-53`). **Still holds,** now through `kolla_toolbox`.
  - fail-fast guards (`roles/mariadb/tasks/lookup_cluster.yml:36-43`, `:73-79`). **Still holds.**
  - recovery takes the whole cluster down: the stop task runs on every MariaDB host when no recovery host is given
    (`roles/mariadb/tasks/recover_cluster.yml:18-25`, `:95-96`). **Still holds.**
  - recovery assumptions: fixed `/tmp` files on the host (`roles/mariadb/tasks/recover_cluster.yml:45-62`) and on the
    Ansible control host (`:7-16`; `roles/mariadb/defaults/main.yml:113`). **Still holds.**
  - upgrade: `upgrade_mariadb` runs in the post-configuration play, which has no `serial`, so on all nodes at once
    (`mariadb.yml:70-92`, `roles/mariadb/tasks/post-upgrade.yml:2-24`). **Still holds.**
  - backup: **changed in 2025.1**, the client now connects to the backup host's own address
    (`roles/mariadb/templates/backup.my.cnf.j2:5-6`), run on the first shard host
    (`roles/mariadb/defaults/main.yml:123`).
  - credentials: **changed in 2025.1**, most logins go through `kolla_toolbox` module arguments
    (`roles/mariadb/tasks/restart_services.yml:31-42`); only the recovery's `pc.bootstrap` still runs
    `mariadb -uroot -p...` in the container (`roles/mariadb/tasks/recover_cluster.yml:149`).
  - scale-out restarts the whole cluster, batch by batch: `wsrep_cluster_address` lists every shard host
    (`roles/mariadb/templates/galera.cnf.j2:33`), so every existing node's `galera.cnf` changes and the compare
    notifies `Restart mariadb container`. **Still holds.**
  - **new:** `mariadb_backup_target` is defined but never read, and the image's replica backup script is never called
    (`group_vars/all.yml:555`; `roles/mariadb/tasks/backup.yml:16`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 10 and 16: recursive chown on data volumes
  at every start, the MariaDB datadir among them (`roles/mariadb/templates/mariadb.json.j2:31-43`) [CODE]; MariaDB has
  no automatic Galera recovery.
- [R20](../risk/risk-register.md#r20): a Glance reconfigure or deploy toggles the global MariaDB
  `log_bin_trust_function_creators` 1→0 around db sync (`roles/glance/tasks/bootstrap_service.yml:2-54`) [CODE].
  **Still holds in 2025.1.**

### Changed in 2025.1

- **ProxySQL by default, no clustercheck by default**, and its removal on `upgrade` ([Impact and
  risk](#impact-and-risk)).
- **Restart decision moved to `service-check-containers`**; the handlers listen to `Restart mariadb container` and lost
  their `config` guard (`roles/mariadb/handlers/main.yml:59-74`) [CODE].
- **WSREP waits and checks through `kolla_toolbox mysql_query`** to the node itself (`roles/mariadb/tasks/lookup_cluster.yml:45-71`,
  `roles/mariadb/tasks/restart_services.yml:31-53`, `roles/mariadb/tasks/check.yml:6-22`) [CODE].
- **`galera.cnf` and command:** 2 GB InnoDB redo log, TLS lines with ProxySQL backend TLS, `mariadbd-safe`
  (`roles/mariadb/templates/galera.cnf.j2:14-18,61`; `roles/mariadb/templates/mariadb.json.j2:3,11-29`) [CODE].
- **Monitor user** with `USAGE,REPLICATION CLIENT` (`roles/mariadb/tasks/register.yml:32`,
  `roles/mariadb/tasks/loadbalancer.yml:34`) [CODE].
- **Recovery** uses the `mariadb` client and no longer starts disabled services
  (`roles/mariadb/tasks/recover_cluster.yml:149,186,217`) [CODE]; the lookup message names `mariadb-recovery`
  (`roles/mariadb/tasks/lookup_cluster.yml:38`).
- **Container engine migration** goes through recovery ([Before and after a run](#before-and-after-a-run)).
- **Clustercheck image:** `socat_wrapper` is now used (`roles/mariadb/templates/mariadb-clustercheck.json.j2:2`) [CODE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py mariadb -->

| Item | Value |
|---|---|
| Play | mariadb.yml (`import_playbook` at site.yml:415; 5 plays) |
| Tags | mariadb |
| Play host patterns | mariadb, mariadb_restart, mariadb_start, mariadb_bootstrap_restart |
| Node types in play (example inventory) | control |
| Node types running its containers | – |
| Containers | `mariadb`, `mariadb_clustercheck` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → recover_cluster (if) → bootstrap |
| Task files | backup.yml, bootstrap.yml, bootstrap_cluster.yml, check-containers.yml, check.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, lookup_cluster.yml, main.yml, post-deploy.yml, post-upgrade.yml, precheck.yml, pull.yml, reconfigure.yml, recover_cluster.yml, register.yml, restart_services.yml, stop.yml, upgrade.yml |
| Templates | `backup.my.cnf.j2`, `galera.cnf.j2`, `hostname.j2`, `mariabackup.json.j2`, `mariadb-clustercheck.json.j2`, `mariadb.json.j2` |
| Handlers (definition order) | Starting first MariaDB container; Wait for first MariaDB service port liveness; Wait for first MariaDB service to sync WSREP; Ensure MariaDB is running normally on bootstrap host; Restart MariaDB on existing cluster members; Start MariaDB on new nodes; Restart mariadb-clustercheck container |
| Key variables | `enable_mariadb`, `mariadb_*`, `database_address`, `enable_external_mariadb_load_balancer` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Database operations](../operations/database-operations.md) — the `mariadb-backup` and `mariadb-recovery` command
  lines
- [Change control-plane membership](../operations/change-control-plane-membership.md) — Galera membership changes
  restart all DB nodes
- [Stop and destroy](../operations/stop-and-destroy.md) — after `kolla-ansible stop`, MariaDB needs `mariadb-recovery`
- [HAProxy + Keepalived](haproxy-keepalived.md) — the database is reached through the internal VIP and ProxySQL, or
  HAProxy
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `serial` and
  `max_fail_percentage` across plays
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
