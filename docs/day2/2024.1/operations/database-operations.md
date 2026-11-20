---
title: Database operations
description: The 2024.1 mariadb_backup and mariadb_recovery command lines, what their playbooks run, and the risk item and fact-sheet sections behind them.
tags: [mariadb, mariadb-backup, mariadb-recovery, risk]
impact: [recovery]
---

# Database operations

The command lines of the MariaDB backup (`mariadb_backup`) and of the Galera cluster recovery (`mariadb_recovery`) in
2024.1, with what changed since 2023.1. What the two playbooks do in detail is described in the sections listed under
[Related](#related).

> [!WARNING]
> `mariadb_recovery` stops every MariaDB node, even healthy ones, and bootstraps from the highest seqno: a full DB
> outage ([R18](../risk/risk-register.md#r18)). The stop and the seqno comparison run only when
> `mariadb_recover_inventory_name` is not set; with `-e mariadb_recover_inventory_name=<host>` the playbook bootstraps
> from that host directly (`roles/mariadb/tasks/recover_cluster.yml:18-96`,
> `roles/mariadb/tasks/recover_cluster.yml:98-100`) [CODE]. The precautions of R18 are "Only when the cluster is
> fully down; identify the node with the highest seqno manually first".

```bash
kolla-ansible -i multinode mariadb_backup               # full (default) or --incremental
kolla-ansible -i multinode mariadb_recovery             # ONLY when the whole Galera cluster is down
```

[CODE] `mariadb_backup` runs `mariadb_backup.yml` with `kolla_action=backup` and `mariadb_backup_type` set by
`--full` (default) or `--incremental`; `mariadb_recovery` runs `mariadb_recovery.yml` with `kolla_action=deploy` and
`mariadb_recover: true` (`tools/kolla-ansible:186-190`, `tools/kolla-ansible:292`, `tools/kolla-ansible:401-409`,
`tools/kolla-ansible:448-456`; `mariadb_backup.yml:1-11`; `mariadb_recovery.yml:1-13`). **Still holds in 2024.1.**
**New in 2024.1:** both plays set `max_fail_percentage`, from `mariadb_backup_max_fail_percentage` or
`mariadb_recovery_max_fail_percentage`, then `kolla_max_fail_percentage`, then 100 (`mariadb_backup.yml:4-7`,
`mariadb_recovery.yml:4-7`); with the default 100 nothing changes ([Write config first, apply in controlled batches
§1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

**Backup.** [CODE] The backup runs on the first host of each MariaDB shard group (`mariadb_backup_host`,
`roles/mariadb/defaults/main.yml:123`; one shard, hence the first `mariadb` host, unless `mariadb_shard_id` is set per
host, `group_vars/all.yml:476-480`); with HAProxy only the default shard qualifies
(`mariadb_backup_possible`, `roles/mariadb/defaults/main.yml:127`). It runs in a one-shot `mariabackup` container
started from the image of the running MariaDB container, or the configured image when there is none
(`roles/mariadb/tasks/backup.yml:2-35`), which writes to the `mariadb_backup` volume
(`roles/mariadb/tasks/backup.yml:31`) with `kolla_mariadb_backup.sh` (`roles/mariadb/tasks/backup.yml:15`): a full
backup streams `mariabackup --backup` through `gzip` and records the date in `last_full_date`, an incremental one
reuses that date as its history name (kolla `docker/mariadb/mariadb-server/backup.sh:7-35`). **Still holds in
2024.1.** The play runs the role only when `enable_mariabackup` is on (default `no`, `group_vars/all.yml:804`;
`mariadb_backup.yml:8-11`). The backup's `my.cnf`, its `config.json` and the backup user are not created by the
backup play: they come from the config and post-deploy steps of a deploy or reconfigure run with
`enable_mariabackup: yes` (`roles/mariadb/tasks/config.yml:15-40`, `roles/mariadb/tasks/config.yml:55-65`,
`roles/mariadb/tasks/register.yml:36-72`, `mariadb.yml:82-86`) [CODE].

**Changed in 2024.1** [CODE]:

- The backup schema is `mysql` instead of `PERCONA_SCHEMA` (`roles/mariadb/defaults/main.yml:124`), and the task that
  created that database is gone. The backup user now gets `RELOAD,PROCESS,LOCK TABLES,BINLOG MONITOR` on `*.*` plus
  `CREATE,ALTER,INSERT` on `mysql.mariadb_backup_history` (`roles/mariadb/tasks/register.yml:49`), instead of the 2023.1
  list that also held `CREATE TABLESPACE` and `SUPER`; the following task still grants `CREATE,INSERT,SELECT` on the
  backup schema, now `mysql.*` (`roles/mariadb/tasks/register.yml:55-72`). Both tasks use `append_privs: True`
  (`roles/mariadb/tasks/register.yml:50`, `roles/mariadb/tasks/register.yml:69`). No task of the 2024.1 tree drops the
  2023.1 `PERCONA_SCHEMA` database or revokes the old privileges (no `percona` match under `ansible/`); whether
  `append_privs` keeps them on an upgraded cluster is module behaviour, [NOT AVAILABLE] from these sources.
- The backup client still connects to `database_address:database_port` (`roles/mariadb/templates/backup.my.cnf.j2:5-6`),
  the internal FQDN (`group_vars/all.yml:83`), while it copies the local datadir mounted at `/var/lib/mysql`
  (`roles/mariadb/tasks/backup.yml:30`). With HAProxy the only non-`backup` member is the first host of the default
  shard (`roles/mariadb/defaults/main.yml:64`), the same host as `mariadb_backup_host`; with ProxySQL the backup user
  is `backup_shard_<id>` (`roles/mariadb/defaults/main.yml:125`), routed to its shard's writer hostgroup
  (`kolla_ansible/database_shards.py:118-127`, `roles/proxysql-config/templates/users.yaml.j2:17-25`). What
  mariabackup does when the server it talks to is not the local one is [NOT AVAILABLE].
- The kolla image ships a second script, `kolla_mariadb_backup_replica.sh`, which picks another Galera node than the
  one that answers and points the backup at it (kolla `docker/mariadb/mariadb-server/backup_replica.sh:78-116`,
  kolla `docker/mariadb/mariadb-server/Dockerfile.j2:42`). Kolla-Ansible 2024.1 does not call it: the backup task runs
  `kolla_mariadb_backup.sh` (`roles/mariadb/tasks/backup.yml:15`), and no file under `ansible/` names the replica
  script.

**Recovery.** [CODE] The recovery play applies the whole role with `kolla_action=deploy`, so config and
check-containers run first, then `bootstrap.yml` skips the fail-fast guards and includes `recover_cluster.yml`
(`roles/mariadb/tasks/deploy.yml:1-6`, `roles/mariadb/tasks/bootstrap.yml:1-10`,
`roles/mariadb/tasks/lookup_cluster.yml:80`). Without a given host, every node is stopped, runs a
`mariadb_wsrep_recovery` one-shot with `--wsrep-recover`, and the seqno read from its log is compared across the shard
group; the host that sees no larger seqno writes its name to a file on the Ansible control host
(`roles/mariadb/tasks/recover_cluster.yml:18-96`). The bootstrap host gets `safe_to_bootstrap: 1` in `grastate.dat`,
starts with `--wsrep-new-cluster` and is set primary; the others start, then the bootstrap host is restarted normally
(`roles/mariadb/tasks/recover_cluster.yml:102-232`), and the run waits for the database through the VIP
(`roles/mariadb/tasks/recover_cluster.yml:234`, `roles/mariadb/tasks/check.yml:5-16`). **Still holds in 2024.1.**
**Changed in 2024.1:** the log copy and `grastate.dat` use `container_engine_volumes_path`
(`roles/mariadb/tasks/recover_cluster.yml:47`, `roles/mariadb/tasks/recover_cluster.yml:106`), which is
`/var/lib/docker/volumes` for Docker and `/var/lib/containers/storage/volumes` for Podman unless
`docker_runtime_directory` is set (`group_vars/all.yml:156-158`); 2023.1 hard-coded the Docker path. The stop now
passes `common_options` (`roles/mariadb/tasks/recover_cluster.yml:24`). Clustercheck is still started on recovery
even when it is disabled (`roles/mariadb/tasks/recover_cluster.yml:172-186`,
`roles/mariadb/tasks/recover_cluster.yml:203-217`).

## Related

- [R18](../risk/risk-register.md#r18) — `mariadb_recovery`: what happens, blast radius and precautions
- [R15](../risk/risk-register.md#r15) — after `kolla-ansible stop`, MariaDB needs `mariadb_recovery`
- [Fact sheet E
  §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)
  — the two playbooks: the backup runs only on the first host of the shard group and requires
  `enable_mariabackup: yes` (default `no`, `group_vars/all.yml:804`; `mariadb_backup.yml:8-11`); otherwise every task
  is skipped silently
- [Fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action) — the rows
  "backup" and "recovery" of the task flow, and the recovery steps in order
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  items 4 to 7 and 9: the fail-fast guards, and what recovery and backup do
- [Write config first, apply in controlled batches](controlled-batches.md) — what `max_fail_percentage` does
- [Pre-execution checklist](pre-execution-checklist.md) — step 8 lists a MariaDB backup as rollback material
- [MariaDB/Galera](../components/mariadb.md) — the component page: fact sheet, tag, risks, service card
