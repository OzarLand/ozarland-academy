---
title: Database operations
description: The 2025.1 mariadb-backup and mariadb-recovery command lines, what their playbooks run, and the risk item and fact-sheet sections behind them.
tags: [mariadb, mariadb-backup, mariadb-recovery, risk]
impact: [recovery]
---

# Database operations

The command lines of the MariaDB backup (`mariadb-backup`) and of the Galera cluster recovery (`mariadb-recovery`) in
2025.1, with what changed since 2024.1. What the two playbooks do in detail is described in the sections listed under
[Related](#related).

> [!WARNING]
> `mariadb-recovery` stops every MariaDB node, even healthy ones, and bootstraps from the highest seqno: a full DB
> outage ([R18](../risk/risk-register.md#r18)). The stop and the seqno comparison run only when
> `mariadb_recover_inventory_name` is not set; with `-e mariadb_recover_inventory_name=<host>` the playbook bootstraps
> from that host directly (`roles/mariadb/tasks/recover_cluster.yml:18-96`,
> `roles/mariadb/tasks/recover_cluster.yml:98-100`) [CODE]. The precautions of R18 are "Only when the cluster is
> fully down; identify the node with the highest seqno manually first".

```bash
kolla-ansible mariadb-backup -i multinode               # full (default) or --incremental
kolla-ansible mariadb-recovery -i multinode             # ONLY when the whole Galera cluster is down
```

**Changed in 2025.1: the command names** [CODE]. The Python command line registers `mariadb-backup` and
`mariadb-recovery`, with hyphens (`setup.cfg:72-73`); the 2024.1 names `mariadb_backup` and `mariadb_recovery` are not
registered any more, so scripts and cron entries that call them must be updated. `mariadb-backup` runs
`mariadb_backup.yml` with `kolla_action=backup` and `mariadb_backup_type` set by `--full` (default) or `--incremental`
(`kolla_ansible/cli/commands.py:437-467`); `mariadb-recovery` runs `mariadb_recovery.yml` with `kolla_action=deploy`
(`kolla_ansible/cli/commands.py:470-481`), and the playbook itself sets `mariadb_recover: true`
(`mariadb_recovery.yml:12-13`). **Still holds in 2025.1:** both plays set `max_fail_percentage`, from
`mariadb_backup_max_fail_percentage` or `mariadb_recovery_max_fail_percentage`, then `kolla_max_fail_percentage`, then
100 (`mariadb_backup.yml:4-7`, `mariadb_recovery.yml:4-7`); with the default 100 nothing changes ([Write config first,
apply in controlled batches §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

**Backup.** [CODE] The backup runs on the first host of each MariaDB shard group (`mariadb_backup_host`,
`roles/mariadb/defaults/main.yml:123`; one shard, hence the first `mariadb` host, unless `mariadb_shard_id` is set per
host, `group_vars/all.yml:550-552`); with HAProxy only the default shard qualifies
(`mariadb_backup_possible`, `roles/mariadb/defaults/main.yml:127`). It runs in a one-shot `mariabackup` container
started from the image of the running MariaDB container, or the configured image when there is none
(`roles/mariadb/tasks/backup.yml:2-36`), which writes to the `mariadb_backup` volume
(`roles/mariadb/tasks/backup.yml:32`) with `kolla_mariadb_backup.sh` (`roles/mariadb/tasks/backup.yml:16`). The play
runs the role only when `enable_mariabackup` is on (default `no`, `group_vars/all.yml:922`; `mariadb_backup.yml:8-11`).
The backup's `my.cnf`, its `config.json` and the backup user are not created by the backup play: they come from the
config and post-deploy steps of a deploy or reconfigure run with `enable_mariabackup: yes`
(`roles/mariadb/tasks/config.yml:12-57`, `roles/mariadb/tasks/register.yml:36-72`, `mariadb.yml:82-86`) [CODE]. The
backup schema (`mysql`) and the backup user's privileges are the same as in 2024.1
(`roles/mariadb/defaults/main.yml:124`, `roles/mariadb/tasks/register.yml:49-50`,
`roles/mariadb/tasks/register.yml:68-69`).

**Changed in 2025.1** [CODE]:

- **The backup reads the backup host itself.** The client in `backup.my.cnf` connects to `api_interface_address` and
  `mariadb_port` (`roles/mariadb/templates/backup.my.cnf.j2:5-6`), that is the MariaDB server of the node whose datadir
  the container mounts at `/var/lib/mysql` (`roles/mariadb/tasks/backup.yml:31`). In 2024.1 it went through
  `database_address`, the internal FQDN, so with ProxySQL the server it talked to could be another node. The backup
  user is still `backup` with HAProxy and `backup_shard_<id>` with ProxySQL (`roles/mariadb/defaults/main.yml:125`).
- **New file layout in the `mariadb_backup` volume** (kolla `docker/mariadb/mariadb-server/backup.sh:7-52`). A full
  backup goes to `full-<dd-mm-YYYY-epoch>/mysqlbackup-<dd-mm-YYYY-epoch>.qp.xbc.xbs.gz` and its path is recorded in
  `last_full_file` (`:9-21`); 2024.1 wrote `mysqlbackup-<date>.qp.xbc.xbs.gz` at the top of the volume and recorded the
  date in `last_full_date`. An incremental backup now unpacks the last full backup to a temporary directory, takes a
  delta against it with `--incremental-basedir` and writes it to `incr-<time>-since-<full date>/` (`:25-52`); it
  **fails with "No full backup file found."** when `last_full_file` does not exist (`:28-31`). Consequence: after an
  upgrade from 2024.1, take a full backup before the first incremental one, and update any tooling that reads
  `last_full_date` or expects the old file names. [NOT AVAILABLE] The restore steps for the new layout, and the disk
  space the temporary copy of the full backup needs; to be confirmed by the community.
- **The replica variable is not used.** With ProxySQL `group_vars/all.yml:555` sets `mariadb_backup_target` to
  `replica`, but no task reads it, and the kolla image's `kolla_mariadb_backup_replica.sh` (kolla
  `docker/mariadb/mariadb-server/Dockerfile.j2:42`) is still never called: the backup task runs
  `kolla_mariadb_backup.sh` ([fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 13).

**Recovery.** [CODE] The recovery play applies the whole role with `kolla_action=deploy`, so config and
check-containers run first, then `bootstrap.yml` skips the fail-fast guards and includes `recover_cluster.yml`
(`roles/mariadb/tasks/deploy.yml:1-11`, `roles/mariadb/tasks/bootstrap.yml:1-10`,
`roles/mariadb/tasks/lookup_cluster.yml:81`). Without a given host, every node is stopped, runs a
`mariadb_wsrep_recovery` one-shot with `--wsrep-recover`, and the seqno read from its log is compared across the shard
group; the host that sees no larger seqno writes its name to a file on the Ansible control host
(`roles/mariadb/tasks/recover_cluster.yml:18-96`). The bootstrap host gets `safe_to_bootstrap: 1` in `grastate.dat`,
starts with `--wsrep-new-cluster` and is set primary; the others start, then the bootstrap host is restarted normally
(`roles/mariadb/tasks/recover_cluster.yml:102-235`), and the run ends with `check.yml`
(`roles/mariadb/tasks/recover_cluster.yml:237`). The log copy and `grastate.dat` use `container_engine_volumes_path`
(`roles/mariadb/tasks/recover_cluster.yml:47`, `roles/mariadb/tasks/recover_cluster.yml:106`;
`group_vars/all.yml:165-167`). **Changed in 2025.1:**

- The restarts loop only over the services enabled and mapped to the host
  (`roles/mariadb/tasks/recover_cluster.yml:186`, `roles/mariadb/tasks/recover_cluster.yml:217`), so a disabled
  clustercheck is no longer started on recovery; the 2024.1 bug is fixed.
- The final check queries the node's own address through `kolla_toolbox`, not the VIP, and first runs the
  `service-check` role (`roles/mariadb/tasks/check.yml:1-22`): a recovery can end green while the VIP or ProxySQL does
  not serve the database ([fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities),
  item 14). After a recovery, check a query through the VIP yourself.
- **A deploy can now run the recovery.** `deploy.yml` imports `recover_cluster.yml` when `migration_flag` is defined
  (`roles/mariadb/tasks/deploy.yml:6-9`), which the container-engine migration sets
  (`migrate-container-engine.yml:12-17`). That migration therefore stops every MariaDB node and bootstraps the cluster
  again, with the same outage as `mariadb-recovery`. [NOT AVAILABLE] How long the database is unavailable during a
  migration; to be confirmed by the community.

## Related

- [R18](../risk/risk-register.md#r18) — `mariadb-recovery`: what happens, blast radius and precautions
- [R15](../risk/risk-register.md#r15) — after `kolla-ansible stop`, MariaDB needs `mariadb-recovery`
- [Fact sheet E
  §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)
  — the two playbooks: the backup runs only on the first host of the shard group and requires
  `enable_mariabackup: yes` (default `no`, `group_vars/all.yml:922`; `mariadb_backup.yml:8-11`); otherwise every task
  is skipped silently
- [Fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action) — the rows
  "backup" and "recovery" of the task flow, and the recovery steps in order
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  items 4 to 7, 9, 13 and 14: the fail-fast guards, what recovery and backup do, and the two new oddities
- [Write config first, apply in controlled batches](controlled-batches.md) — what `max_fail_percentage` does
- [Pre-execution checklist](pre-execution-checklist.md) — step 8 lists a MariaDB backup as rollback material
- [MariaDB/Galera](../components/mariadb.md) — the component page: fact sheet, tag, risks, service card
