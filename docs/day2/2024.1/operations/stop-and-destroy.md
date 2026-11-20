---
title: Stop and destroy
description: The stop and destroy command lines in 2024.1, both rated Critical, with max_fail_percentage, the inventory paths destroy keeps, and where each one is described.
tags: [stop, destroy, risk, podman, max-fail-percentage]
impact: [critical]
---

# Stop and destroy

The command lines of `kolla-ansible stop` and `kolla-ansible destroy` in 2024.1, which the study files under
"dangerous", and the changes of 2024.1 that touch them: `max_fail_percentage` on their plays, the inventory paths that
`destroy` now keeps, and the systemd units it now disables. What each command stops or removes in detail is described in
the sections listed under [Related](#related).

> [!CAUTION]
> The risk register rates both commands Critical: `kolla-ansible stop` ([R15](../risk/risk-register.md#r15)) and
> `kolla-ansible destroy` ([R16](../risk/risk-register.md#r16)). `destroy` targets `hosts: all`, which includes the
> deploy host (`destroy.yml:2-3`, `inventory/multinode:32-33`); only what you pass with `--limit` narrows it. Never run
> it on production.

```bash
kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03
kolla-ansible -i multinode destroy --yes-i-really-really-mean-it   # never on production
```

- **Confirmation.** Both refuse to run without `--yes-i-really-really-mean-it` [CODE] (kolla-ansible
  `tools/kolla-ansible:475-483, :536-544`; the flag is taken only when it appears in the raw arguments, `:342-348`).
  `stop` runs `site.yml` with `kolla_action=stop`, so `-t` and `--limit` narrow it; `destroy` runs `destroy.yml`
  (kolla-ansible `tools/kolla-ansible:285, :460, :533-535`).
- **What `stop` does.** Each role's `stop.yml` imports `service-stop`, which runs `kolla_container` `stop_container`
  for each enabled container mapped to the host [CODE] (e.g. `roles/heat/tasks/stop.yml:2-6`,
  `roles/service-stop/tasks/main.yml:2-12`; swift lists its containers itself, `roles/swift/tasks/stop.yml:2-11`). The
  stop goes through the container's systemd unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t
  <graceful_timeout>`, 60 s by default: with Docker when the unit exists, `docker stop` otherwise; with Podman always
  through the unit, except for one-shot containers (`module_utils/kolla_docker_worker.py:415-431`,
  `module_utils/kolla_podman_worker.py:575-593`, `module_utils/kolla_systemd_worker.py:32`, `group_vars/all.yml:139,
  :151`). The stop path does not disable the unit, which `create_unit_file` enabled for `multi-user.target`
  (`module_utils/kolla_systemd_worker.py:37-38, :172-185`). [NOT AVAILABLE] Whether systemd starts a stopped container
  again at the next boot of the host.
- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`) [CODE]
  (`roles/service-stop/tasks/main.yml:10-11`, default `[]` in `group_vars/all.yml:876`).
- **New in 2024.1: `max_fail_percentage` on the plays of both commands.** Every play of `site.yml`, and the single play
  of `destroy.yml`, sets `max_fail_percentage: {{ <svc>_max_fail_percentage | default(kolla_max_fail_percentage) |
  default(100) }}` (e.g. `site.yml:96-99`, `destroy.yml:4-7`) [CODE]. With the default 100, a host that fails drops
  out and the others carry on: ansible-core 2.16.20 breaks a play only when the failed hosts of the current batch
  exceed that share of the batch, and otherwise stops the playbook only when every host of a batch failed
  (`lib/ansible/plugins/strategy/linear.py:336-350`, `lib/ansible/executor/playbook_executor.py:196-209, :219-220`).
  `stop` passes no `kolla_serial` and `destroy.yml` sets no `serial`, so each play runs its hosts in one batch
  (`tools/kolla-ansible:533-535`, `destroy.yml:2-9`). A lower value (`kolla_max_fail_percentage`, or
  `destroy_max_fail_percentage` for `destroy`) ends the run once the share is exceeded; the check comes after the
  task has run on every host of the batch (`lib/ansible/plugins/strategy/linear.py:198, :218-219, :336-350`), so it
  stops the following tasks and plays, not the task that failed.
- **What `destroy` runs.** The role runs, in order, a check that `sudo <engine> ps` works, `tools/cleanup-containers`,
  `tools/cleanup-images` (only with images included) and `tools/cleanup-host` (`roles/destroy/tasks/main.yml:2-8`,
  `roles/destroy/tasks/validate_docker_execute.yml:2-5`, `roles/destroy/tasks/cleanup_containers.yml:2-3`,
  `roles/destroy/tasks/cleanup_images.yml:2-5`, `roles/destroy/tasks/cleanup_host.yml:2-17`) [CODE]. Each script is
  given `kolla_container_engine`, and `cleanup-containers` accepts only `docker` or `podman`
  (`tools/cleanup-containers:4-10`). It exits with an error, before it removes anything, when `nova_libvirt` runs and
  QEMU processes are found (`:16-22`).
- **New in 2024.1: `cleanup-containers` disables the units.** For each Kolla container it disables, stops and, if
  failed, resets `kolla-<name>-container.service`, then removes the containers, their volumes, the `/var/log/kolla`
  link and every `kolla-*-container.service` file (`tools/cleanup-containers:43-67`) [CODE].
- **New in 2024.1: the inventories passed with `-i` are kept.** `destroy` joins every `-i` value into
  `-e inventories_comma_separated=…` (`tools/kolla-ansible:462-466, :474`); the role hands it to `cleanup-host` as
  `kolla_ansible_inventories` (`roles/destroy/tasks/cleanup_host.yml:17`). `cleanup-host` removes every entry of
  `/etc/kolla` except `passwords.yml`, `globals.yml`, `globals.d`, `kolla-build.conf`, `config`, `certificates` and the
  entries equal to one of those inventory values (`tools/cleanup-host:71, :78-103`) [CODE]. The test is a string
  comparison with the full path `/etc/kolla/<name>`, so an inventory is kept only when it was passed by that exact path
  (`-i /etc/kolla/multinode`); a relative `-i multinode` or a path written another way does not match
  (`tools/cleanup-host:79, :82-87`). The variable has no default in the sources: only the CLI sets it.
- `destroy` also removes the images with `--include-images` (or `enable_destroy_images: yes`, default `no`) [CODE]
  (kolla-ansible `tools/kolla-ansible:468-470`; `roles/destroy/defaults/main.yml:2`, `group_vars/all.yml:867`,
  `roles/destroy/tasks/cleanup_images.yml:3-5`; `tools/cleanup-images --all` removes every image with the
  `kolla_version` label, `tools/cleanup-images:60-63, :94`). With `destroy_include_dev`, it removes the dev-mode
  repositories under `kolla_dev_repos_directory` (`roles/destroy/defaults/main.yml:3`,
  `group_vars/all.yml:54`; kolla-ansible `tools/cleanup-host:105-108`).
- **`--include-dev`** sets `-e destroy_include_dev=yes` (`tools/kolla-ansible:471-473`), but the getopt list declares
  it as `include-dev:`, with the colon that marks an option taking a value, while its branch reads no value
  (`tools/kolla-ansible:275, :355-358`). [NOT AVAILABLE] How getopt then parses `--include-dev` on the command line;
  the same spelling is in 2023.1.

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
- [Write config first, apply in controlled batches
  §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage) — how `max_fail_percentage` stops
  a run
- [Fact sheet B
  §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) —
  item 4: after `stop`, the next deploy or reconfigure fails until `mariadb_recovery` is run
- [Database operations](database-operations.md) — the `mariadb_recovery` command
- [Update container images §1.2](update-container-images.md#12-prune-old-images) — `prune-images`, which removes
  images without stopping containers
