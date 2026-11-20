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

- Both refuse to run without `--yes-i-really-really-mean-it` [CODE] (kolla-ansible `tools/kolla-ansible:452-470,
  :519-531`). `stop` runs `site.yml` with `kolla_action=stop`, so `-t` and `--limit` narrow it; `destroy` runs
  `destroy.yml` (kolla-ansible `tools/kolla-ansible:280, :454, :521`).
- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`) [CODE]
  (`roles/service-stop/tasks/main.yml:10-12`, default `[]` in `group_vars/all.yml:784`).
- `destroy` also removes the images with `--include-images` (or `enable_destroy_images: yes`, default `no`), and the
  dev-mode repositories under `kolla_dev_repos_directory` with `--include-dev` [CODE] (kolla-ansible
  `tools/kolla-ansible:455-460`;
  `roles/destroy/defaults/main.yml:2-3`, `group_vars/all.yml:775`, `roles/destroy/tasks/cleanup_images.yml:5`;
  kolla-ansible `tools/cleanup-host:92-95`).

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
