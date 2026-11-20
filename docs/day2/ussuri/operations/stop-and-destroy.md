---
title: Stop and destroy
description: The stop and destroy command lines, both rated Critical in the risk register, with the sections that describe what each one stops or removes.
tags: [stop, destroy, risk]
impact: [critical]
---

# Stop and destroy

The command lines of `kolla-ansible stop` and `kolla-ansible destroy`, which the study files under "dangerous". What
each one stops or removes is described in the sections listed under [Related](#related).

> [!CAUTION]
> The risk register rates both commands Critical: `kolla-ansible stop` ([R15](../risk/risk-register.md#r15)) and
> `kolla-ansible destroy` ([R16](../risk/risk-register.md#r16)). For `destroy`, the precaution of R16 is "Never on
> production; there is no `--limit` safety net beyond what you pass".

```bash
kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03
kolla-ansible -i multinode destroy --yes-i-really-really-mean-it   # never on production
```

- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`).

## Related

- [R15](../risk/risk-register.md#r15) — `kolla-ansible stop`: it stops all Kolla containers on the targeted hosts, and
  MariaDB then needs `mariadb_recovery`
- [R16](../risk/risk-register.md#r16) — `kolla-ansible destroy`: what it removes on the targeted hosts, the deploy
  host included
- [Fact sheet E
  §6](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#6-destroy-ansibledestroyyml-role-destroy-toolscleanup-)
  — `destroy` in detail: `destroy.yml`, the `destroy` role and the `tools/cleanup-*` scripts
- [Fact sheet E §11](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#11-toolskolla-ansible-cli) — the
  confirmation guard `--yes-i-really-really-mean-it`
- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the row
  `stop` of the action matrix
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  item 4: after `stop`, the next deploy or reconfigure fails until `mariadb_recovery` is run
- [Database operations](database-operations.md) — the `mariadb_recovery` command
