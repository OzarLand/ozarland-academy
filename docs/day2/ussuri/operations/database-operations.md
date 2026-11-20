---
title: Database operations
description: The mariadb_backup and mariadb_recovery command lines, with the risk item and the fact-sheet sections that describe the two playbooks.
tags: [mariadb, mariadb-backup, mariadb-recovery, risk]
impact: [recovery]
---

# Database operations

The command lines of the MariaDB backup (`mariadb_backup`) and of the Galera cluster recovery (`mariadb_recovery`). What
the two playbooks do is described in the sections listed under [Related](#related).

> [!WARNING]
> `mariadb_recovery` stops every MariaDB node, even healthy ones, and bootstraps from the highest seqno: a full DB
> outage ([R18](../risk/risk-register.md#r18)). The precautions of R18 are "Only when the cluster is fully down;
> identify the node with the highest seqno manually first".

```bash
kolla-ansible -i multinode mariadb_backup               # full (default) or --incremental
kolla-ansible -i multinode mariadb_recovery             # ONLY when the whole Galera cluster is down
```

## Related

- [R18](../risk/risk-register.md#r18) — `mariadb_recovery`: what happens, blast radius and precautions
- [R15](../risk/risk-register.md#r15) — after `kolla-ansible stop`, MariaDB needs `mariadb_recovery`
- [Fact sheet E
  §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only)
  — the two playbooks: the backup runs only on the first `mariadb` host and requires `enable_mariabackup: yes` (default
  `no`); otherwise every task is skipped silently
- [Fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action) — the rows
  "backup" and "recovery" of the task flow, and the recovery steps in order
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  items 4 to 7 and 9: the fail-fast guards, and what recovery and backup do
- [Pre-execution checklist](pre-execution-checklist.md) — step 8 lists a MariaDB backup as rollback material
- [MariaDB/Galera](../components/mariadb.md) — the component page: fact sheet, tag, risks, service card
